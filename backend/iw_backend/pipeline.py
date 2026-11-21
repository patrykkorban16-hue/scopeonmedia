"""Pipeline: pobrana strona/post → Object Storage → silnik AI (preprocessing) → deduplikacja → baza treści →
silnik AI (moduły 1–3 + agregator) → ujednolicone wyniki → alerty WebSocket → (asynchronicznie) ocena LLM."""
from __future__ import annotations

import json
import logging
import time

from sqlalchemy import select

from . import ai_client, config, registry
from .db import Content, Document, Finding, get_thresholds, risk_level, session_scope, utcnow
from .events import publish
from .serializers import finding_dict
from .storage import put_content_addressed

log = logging.getLogger(__name__)
NEAR_DUP_BITS = 3
# Moduły, w których ocena LLM współtworzy score. M2: tylko opinia doradcza – kryteria 4–8 dotyczą prezentacji
# wizualnej (czcionka, kontrast, ukrycie, responsywność), której model tekstowy nie widzi.
LLM_BLEND_MODULES = {1, 3}
INJECTION_REASON = {"rule": "llm:prompt_injection", "label": "treść próbuje sterować modelem AI (prompt injection)",
                    "evidence": "ocena LLM pominięta – materiał wymaga ręcznej weryfikacji", "weight": 0.0}


def blend_llm(rule_score: float, p: float, weight: float, max_decrease: float) -> float:
    """Ta sama formuła co w silniku AI: LLM podnosi wynik swobodnie, obniża najwyżej o max_decrease."""
    return max((1 - weight) * rule_score + weight * p, rule_score - max_decrease)
_llm_cache = {"at": 0.0, "ok": False}


def llm_available() -> bool:
    if time.time() - _llm_cache["at"] > 60:
        h = ai_client.health()
        _llm_cache.update(at=time.time(), ok=bool(h.get("llm", {}).get("available")))
    return _llm_cache["ok"]


def needs_llm(f: Finding, uf: dict) -> bool:
    """Czy zlecić automatyczną ocenę LLM (tryb z konfiguracji; ocena już wykonana nie jest powtarzana)."""
    if config.LLM_REVIEW_MODE == "off" or not uf.get("llm_eligible", True) or (f.llm or {}).get("status") == "done":
        return False
    if config.LLM_REVIEW_MODE == "uncertain" and not (config.LLM_BAND[0] <= uf["rule_score"] <= config.LLM_BAND[1]):
        return False
    return llm_available()


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def ingest(page: dict, job_id: int | None = None) -> tuple[int | None, str]:
    """Zwraca (document_id, wynik): new | updated | unchanged | duplicate | skipped."""
    meta = page["meta"]
    if page.get("html") is not None:
        raw_key = put_content_addressed(page["html"].encode("utf-8"), "raw", "html", "text/html")
    else:
        raw_key = put_content_addressed(page["raw"], "raw", "json", "application/json")
    shots = {vp: put_content_addressed(png, "screenshots", "png", "image/png")
             for vp, png in (page.get("screenshots") or {}).items()}
    pre = ai_client.preprocess(meta["url"], meta["source_type"], html=page.get("html"), text=page.get("text"),
                               render=page.get("render"))
    if len(pre["text"]) < 40:
        return None, "skipped"
    now = utcnow()
    with session_scope() as s:
        doc = s.scalar(select(Document).where(Document.url == meta["url"]))
        if doc is not None and doc.content_hash == pre["content_hash"]:
            doc.last_seen_at, doc.availability, doc.http_status = now, "online", page.get("status")
            if shots:
                doc.screenshots = shots
            return doc.id, "unchanged"
        outcome = "new" if doc is None else "updated"
        dup_of, near = None, []
        for oid, odomain, ohash, osim in s.execute(
                select(Document.id, Document.domain, Document.content_hash, Document.simhash)
                .where(Document.url != meta["url"], Document.duplicate_of.is_(None)).order_by(Document.id.desc()).limit(20000)):
            same = ohash == pre["content_hash"] or (osim and _hamming(osim, pre["simhash"]) <= NEAR_DUP_BITS)
            if not same:
                continue
            if odomain == meta["domain"]:
                dup_of = oid                     # ten sam materiał pod innym adresem w tym samym serwisie
                break
            near.append(oid)                     # ten sam przekaz u innego nadawcy → sygnał kampanii
        if doc is None:
            doc = Document(url=meta["url"], first_seen_at=now)
            s.add(doc)
        doc.fetched_url = meta.get("fetched_url") or meta["url"]
        doc.domain, doc.source_type = meta["domain"], meta["source_type"]
        doc.title = (meta.get("title") or "")[:1000]
        doc.author, doc.author_url = meta.get("author"), meta.get("author_url")
        doc.language = pre["language"]
        doc.published_at = meta.get("published_at")
        doc.last_seen_at, doc.availability, doc.http_status = now, "online", page.get("status")
        doc.content_hash, doc.simhash, doc.raw_key = pre["content_hash"], pre["simhash"], raw_key
        doc.screenshots = shots or doc.screenshots or {}
        doc.duplicate_of, doc.crawl_job_id = dup_of, job_id
        doc.ground_truth = meta.get("ground_truth") or {}
        doc.meta = json.loads(json.dumps({k: meta.get(k) for k in ("site_name", "description", "links", "metrics", "ad_meta")}
                                         | {"near_duplicates": near[:20]}, default=str))
        s.flush()
        stored_pre = {k: v for k, v in pre.items() if k not in ("embedding", "tokens", "text", "normalized")}
        if doc.content is None:
            doc.content = Content(text="", tokens=[])
        doc.content.text = pre["text"]
        doc.content.tokens = pre["tokens"][:2000]
        doc.content.token_count = pre["token_count"]
        doc.content.embedding = pre["embedding"]
        doc.content.embedding_model = pre["embedding_model"]
        doc.content.preprocessed = stored_pre
        return doc.id, ("duplicate" if dup_of else outcome)


def analyze_document(doc_id: int) -> tuple[list[dict], list[int]]:
    """Analiza w silniku AI i zapis ujednoliconych wyników. Zwraca (zdarzenia, id wyników do oceny LLM)."""
    with session_scope() as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.content is None or doc.duplicate_of:
            return [], []
        document = {"id": doc.id, "url": doc.url, "domain": doc.domain, "source_type": doc.source_type,
                    "title": doc.title, "author": doc.author, "author_url": doc.author_url,
                    "site_name": (doc.meta or {}).get("site_name"),
                    "published_at": doc.published_at.isoformat() if doc.published_at else None,
                    "links": (doc.meta or {}).get("links") or [], "metrics": (doc.meta or {}).get("metrics") or {}}
        pre = dict(doc.content.preprocessed, text=doc.content.text, normalized="", tokens=[],
                   embedding=doc.content.embedding or [], embedding_model=doc.content.embedding_model or "")
    result = ai_client.analyze(document, pre, registry.version())
    events, llm_ids = [], []
    with session_scope() as s:
        doc = s.get(Document, doc_id)
        th = get_thresholds(s)
        seen_modules = set()
        for uf in result["findings"]:
            m = uf["module"]
            seen_modules.add(m)
            f = s.scalar(select(Finding).where(Finding.document_id == doc_id, Finding.module == m))
            is_new = f is None
            if is_new:
                f = Finding(document_id=doc_id, module=m, status="new", llm={})
                s.add(f)
            f.category, f.rule_score = uf["category"], uf["rule_score"]
            # ponowna analiza zachowuje wcześniejszą ocenę LLM (ta sama formuła mieszania co w silniku AI)
            llm = f.llm or {}
            f.score = uf["score"] if (f.llm_score is None or m not in LLM_BLEND_MODULES) else round(blend_llm(
                uf["rule_score"], f.llm_score, float(llm.get("weight") or 0.0), float(llm.get("max_decrease") or 0.0)), 4)
            f.firm, f.advertiser, f.entity = uf.get("firm") or {}, uf.get("advertiser") or {}, uf.get("entity") or {}
            f.excerpt, f.reasons, f.rules, f.details = uf["excerpt"][:3000], uf["reasons"], uf["rules"], uf["details"]
            if llm.get("status") == "skipped_injection":
                f.reasons = [*f.reasons, INJECTION_REASON]
            f.event_date = doc.published_at or doc.first_seen_at
            gt = (doc.ground_truth or {}).get(str(m))
            f.ground_truth = None if gt is None else bool(gt)
            s.flush()
            payload = finding_dict(f, doc, th)
            if risk_level(f.score, th[m]) == "high" and f.alerted_at is None:
                f.alerted_at = utcnow()
                events.append({"type": "alert", "data": payload})
            elif not is_new:
                events.append({"type": "finding_updated", "data": payload})
            if needs_llm(f, uf):
                f.llm = {"status": "queued"}
                llm_ids.append(f.id)
        # moduł przestał mieć zastosowanie (np. po zmianie rejestru) – usuń wynik, jeśli analityk go nie ruszał
        for f in s.scalars(select(Finding).where(Finding.document_id == doc_id)):
            if f.module not in seen_modules and f.status == "new":
                s.delete(f)
    return events, llm_ids


def llm_review(finding_id: int) -> list[dict]:
    with session_scope() as s:
        f = s.get(Finding, finding_id)
        if f is None:
            return []
        d = f.document
        ctx = f"źródło: {d.source_type}; domena: {d.domain}; autor: {d.author or '-'}; firma: {(f.firm or {}).get('name', '-')}"
        text, module, rule_score = d.content.text if d.content else f.excerpt, f.module, f.rule_score
        f.llm = {"status": "running"}
    try:
        r = ai_client.llm_review(module, text, ctx, rule_score)
    except Exception as exc:
        r = {"available": False, "error": str(exc)[:200]}
    events = []
    with session_scope() as s:
        f = s.get(Finding, finding_id)
        th = get_thresholds(s)
        if r.get("probability") is not None:
            blend = f.module in LLM_BLEND_MODULES
            f.llm_score = r["probability"]
            if blend:
                f.score = r["score"]
            f.llm = {"status": "done", "model": r.get("model"), "probability": r["probability"],
                     "weight": r.get("weight") if blend else 0.0, "max_decrease": r.get("max_decrease") or 0.0,
                     "advisory": not blend, "reasons": r.get("reasons", []), "at": utcnow().isoformat()}
        elif r.get("injection_suspected"):
            # treść próbuje sterować modelem – LLM pominięty, a fakt próby trafia do analityka jako sygnał
            f.llm = {"status": "skipped_injection", "error": r.get("error")}
            if not any(x.get("rule") == INJECTION_REASON["rule"] for x in f.reasons):
                f.reasons = [*f.reasons, INJECTION_REASON]
        else:
            f.llm = {"status": "unavailable", "error": r.get("error")}
        s.flush()
        payload = finding_dict(f, f.document, th)
        if risk_level(f.score, th[f.module]) == "high" and f.alerted_at is None:
            f.alerted_at = utcnow()
            events.append({"type": "alert", "data": payload})
        events.append({"type": "finding_updated", "data": payload})
    publish(events)
    return events
