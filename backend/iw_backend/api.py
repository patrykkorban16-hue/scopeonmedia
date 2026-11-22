"""REST API + WebSocket (Socket.IO) dla dashboardu.

    uvicorn iw_backend.api:asgi --port 8000
"""
from __future__ import annotations

import csv
import io
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import socketio
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from . import __version__, ai_client, config, registry
from .db import (Content, CrawlJob, Document, Entity, Finding, StatusHistory, get_setting, get_thresholds, high_cut,
                 init_db, risk_level, session_scope, set_threshold, utcnow)
from .security import csv_safe, fetch_allowed
from .serializers import MODULE_NAMES, finding_dict, iso
from .storage import get_storage

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
STATUSES = ["new", "in_review", "confirmed", "false_positive", "closed"]
DEMO_DIR = Path(__file__).parent / "demo"


@asynccontextmanager
async def lifespan(_app):
    config.require_internal_token()
    init_db()
    with session_scope() as s:
        empty = not s.scalar(select(func.count()).select_from(Entity))
    if empty and "demo" in config.REGISTRY_SOURCES:
        registry.load_demo()
    yield


sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=config.CORS_ORIGINS, logger=False, engineio_logger=False)
app = FastAPI(title="ScopeOnMedia API", version=__version__, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST", "PUT", "PATCH"],
                   allow_headers=["Content-Type"])
(DEMO_DIR / "sites").mkdir(parents=True, exist_ok=True)
app.mount("/demo/sites", StaticFiles(directory=DEMO_DIR / "sites", html=True), name="demo-sites")


def _check_internal(token: str) -> None:
    if not config.INTERNAL_TOKEN or not secrets.compare_digest(token, config.INTERNAL_TOKEN):
        raise HTTPException(403, "brak dostępu")


def _date(v: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(v) if v else None
    except ValueError:
        raise HTTPException(400, f"nieprawidłowa data: {v}") from None


# ------------------------------------------------------------------------------ filtry
class Filters:
    def __init__(self, module: list[int], source: list[str], risk: list[str], status: list[str],
                 date_from: str | None, date_to: str | None, q: str | None, date_field: str = "event"):
        self.module, self.source, self.risk, self.status = module, source, risk, status
        self.date_from, self.date_to, self.q = _date(date_from), _date(date_to), (q or "").strip()
        self.date_col = Finding.created_at if date_field == "detected" else Finding.event_date

    def apply(self, stmt, th: dict[int, float], with_risk: bool = True):
        if self.module:
            stmt = stmt.where(Finding.module.in_(self.module))
        if self.source:
            stmt = stmt.where(Document.source_type.in_(self.source))
        if self.status:
            stmt = stmt.where(Finding.status.in_(self.status))
        if with_risk and self.risk and set(self.risk) != {"high", "medium", "low"}:
            parts = []
            for m, t in th.items():
                conds = []
                if "high" in self.risk:
                    conds.append(Finding.score >= high_cut(t))
                if "medium" in self.risk:
                    conds.append(and_(Finding.score >= t, Finding.score < high_cut(t)))
                if "low" in self.risk:
                    conds.append(Finding.score < t)
                if conds:
                    parts.append(and_(Finding.module == m, or_(*conds)))
            stmt = stmt.where(or_(*parts)) if parts else stmt.where(False)
        if self.date_from:
            stmt = stmt.where(self.date_col >= self.date_from)
        if self.date_to:
            stmt = stmt.where(self.date_col < self.date_to + timedelta(days=1))
        if self.q:
            like = f"%{self.q.lower()}%"
            stmt = stmt.where(or_(func.lower(Finding.excerpt).like(like), func.lower(Finding.category).like(like),
                                  func.lower(Document.url).like(like), func.lower(func.coalesce(Document.title, "")).like(like),
                                  func.lower(func.coalesce(Document.author, "")).like(like)))
        return stmt


def _filters(module: list[int] = Query(default=[]), source: list[str] = Query(default=[]),
             risk: list[str] = Query(default=["high", "medium"]), status: list[str] = Query(default=[]),
             date_from: str | None = None, date_to: str | None = None, q: str | None = None,
             date_field: str = "event") -> Filters:
    return Filters(module, source, risk, status, date_from, date_to, q, date_field)


def _base():
    return select(Finding, Document).join(Document, Finding.document_id == Document.id)


# ------------------------------------------------------------------------------ wyniki
@app.get("/api/findings")
def list_findings(module: list[int] = Query(default=[]), source: list[str] = Query(default=[]),
                  risk: list[str] = Query(default=["high", "medium"]), status: list[str] = Query(default=[]),
                  date_from: str | None = None, date_to: str | None = None, q: str | None = None,
                  date_field: str = "event", sort: str = "score", limit: int = 100, offset: int = 0):
    flt = _filters(module, source, risk, status, date_from, date_to, q, date_field)
    with session_scope() as s:
        th = get_thresholds(s)
        stmt = flt.apply(_base(), th)
        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        order = {"score": Finding.score.desc(), "date": flt.date_col.desc(), "updated": Finding.updated_at.desc()}
        rows = s.execute(stmt.order_by(order.get(sort, Finding.score.desc()), Finding.id.desc())
                         .limit(max(1, min(limit, 500))).offset(max(0, offset))).all()
        return {"total": total, "items": [finding_dict(f, d, th) for f, d in rows], "thresholds": th}


@app.get("/api/findings/{fid}")
def get_finding(fid: int):
    with session_scope() as s:
        f = s.get(Finding, fid)
        if not f:
            raise HTTPException(404)
        out = finding_dict(f, f.document, get_thresholds(s), full=True)
        out["text"] = f.document.content.text[:12000] if f.document.content else ""
        out["history"] = [{"old": h.old_status, "new": h.new_status, "note": h.note, "at": iso(h.changed_at)}
                          for h in s.scalars(select(StatusHistory).where(StatusHistory.finding_id == fid)
                                             .order_by(StatusHistory.changed_at))]
        return out


@app.get("/api/findings/{fid}/similar")
def similar(fid: int, limit: int = 6):
    """Materiały o zbliżonej treści (podobieństwo embeddingów) – np. ta sama kampania u wielu nadawców."""
    with session_scope() as s:
        f = s.get(Finding, fid)
        if not f or not f.document.content or not f.document.content.embedding:
            return []
        c = f.document.content
        rows = s.execute(select(Content.document_id, Content.embedding).where(
            Content.embedding_model == c.embedding_model, Content.document_id != c.document_id)).all()
        if not rows:
            return []
        q = np.asarray(c.embedding, dtype=np.float32)
        mat = np.asarray([r[1] for r in rows], dtype=np.float32)
        sims = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-9)
        order = np.argsort(-sims)[: limit * 3]
        th = get_thresholds(s)
        out = []
        for i in order:
            doc = s.get(Document, rows[i][0])
            best = max(doc.findings, key=lambda x: x.score, default=None)
            out.append({"document_id": doc.id, "similarity": round(float(sims[i]), 3), "url": doc.url, "title": doc.title,
                        "author": doc.author, "source_type": doc.source_type,
                        "finding": finding_dict(best, doc, th) if best else None})
            if len(out) >= limit:
                break
        return out


class StatusBody(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=4000)


@app.patch("/api/findings/{fid}")
async def update_status(fid: int, body: StatusBody):
    if body.status not in STATUSES:
        raise HTTPException(400, f"status musi być jednym z: {', '.join(STATUSES)}")
    with session_scope() as s:
        f = s.get(Finding, fid)
        if not f:
            raise HTTPException(404)
        if f.status != body.status or body.note:
            s.add(StatusHistory(finding_id=fid, old_status=f.status, new_status=body.status, note=body.note))
        f.status = body.status
        if body.note is not None:
            f.analyst_note = body.note
        s.flush()
        payload = finding_dict(f, f.document, get_thresholds(s))
    await sio.emit("finding_updated", payload)
    return payload


@app.post("/api/findings/{fid}/llm")
async def request_llm(fid: int):
    """Ocena LLM na żądanie analityka (asynchronicznie; wynik przychodzi zdarzeniem finding_updated)."""
    from .tasks import task_llm_review

    with session_scope() as s:
        f = s.get(Finding, fid)
        if not f:
            raise HTTPException(404)
        if (f.llm or {}).get("status") in ("queued", "running"):
            return {"queued": False, "status": f.llm["status"]}
        f.llm = {"status": "queued"}
        s.flush()
        payload = finding_dict(f, f.document, get_thresholds(s))
    task_llm_review(fid)
    await sio.emit("finding_updated", payload)
    return {"queued": True}


# ------------------------------------------------------------------------------ statystyki i trendy
@app.get("/api/stats")
def stats(module: list[int] = Query(default=[]), source: list[str] = Query(default=[]),
          status: list[str] = Query(default=[]), date_from: str | None = None, date_to: str | None = None,
          q: str | None = None, date_field: str = "event"):
    flt = _filters(module, source, [], status, date_from, date_to, q, date_field)
    with session_scope() as s:
        th = get_thresholds(s)
        rows = s.execute(flt.apply(_base(), th, with_risk=False)).all()
        by_module = {m: {"high": 0, "medium": 0, "low": 0, "total": 0} for m in (1, 2, 3)}
        by_source: dict[str, int] = {}
        by_status = {k: 0 for k in STATUSES}
        for f, d in rows:
            lvl = risk_level(f.score, th[f.module])
            by_module[f.module][lvl] += 1
            by_module[f.module]["total"] += 1
            if lvl != "low":
                by_source[d.source_type] = by_source.get(d.source_type, 0) + 1
                by_status[f.status] += 1
        docs = s.scalar(select(func.count()).select_from(Document))
        dups = s.scalar(select(func.count()).select_from(Document).where(Document.duplicate_of.is_not(None)))
        sources = [r for (r,) in s.execute(select(Document.source_type).distinct())]
        return {"by_module": by_module, "by_source": by_source, "by_status": by_status, "documents": docs,
                "duplicates": dups, "thresholds": th, "module_names": MODULE_NAMES, "sources": sorted(sources)}


@app.get("/api/trends")
def trends(module: list[int] = Query(default=[]), source: list[str] = Query(default=[]),
           risk: list[str] = Query(default=["high", "medium"]), status: list[str] = Query(default=[]),
           date_from: str | None = None, date_to: str | None = None, q: str | None = None,
           date_field: str = "event", granularity: str = "day"):
    flt = _filters(module, source, risk, status, date_from, date_to, q, date_field)
    with session_scope() as s:
        th = get_thresholds(s)
        buckets: dict[str, dict] = {}
        for f, _ in s.execute(flt.apply(_base(), th)).all():
            d = f.created_at if date_field == "detected" else f.event_date
            if granularity == "week":
                d = d - timedelta(days=d.weekday())
            k = d.strftime("%Y-%m-%d")
            b = buckets.setdefault(k, {"date": k, "m1": 0, "m2": 0, "m3": 0, "high": 0, "total": 0})
            b[f"m{f.module}"] += 1
            b["total"] += 1
            b["high"] += risk_level(f.score, th[f.module]) == "high"
    if not buckets:
        return []
    keys = sorted(buckets)
    step = timedelta(days=7 if granularity == "week" else 1)
    d, end, out = datetime.fromisoformat(keys[0]), datetime.fromisoformat(keys[-1]), []
    while d <= end and len(out) < 800:
        k = d.strftime("%Y-%m-%d")
        out.append(buckets.get(k, {"date": k, "m1": 0, "m2": 0, "m3": 0, "high": 0, "total": 0}))
        d += step
    return out


# ------------------------------------------------------------------------------ kalibracja
@app.get("/api/thresholds")
def thresholds():
    with session_scope() as s:
        return get_thresholds(s)


class ThresholdBody(BaseModel):
    value: float = Field(ge=0, le=1)


@app.put("/api/thresholds/{module}")
async def put_threshold(module: int, body: ThresholdBody):
    if module not in (1, 2, 3):
        raise HTTPException(400, "moduł 1, 2 lub 3")
    with session_scope() as s:
        th = set_threshold(s, module, body.value)
    await sio.emit("thresholds", th)
    return th


def _label(f: Finding) -> bool | None:
    if f.status == "confirmed":
        return True
    if f.status == "false_positive":
        return False
    return f.ground_truth


@app.get("/api/calibration/{module}")
def calibration(module: int):
    if module not in (1, 2, 3):
        raise HTTPException(400)
    with session_scope() as s:
        th = get_thresholds(s)[module]
        rows = [(f.score, _label(f)) for f in s.scalars(select(Finding).where(Finding.module == module))]
    labeled = [(sc, y) for sc, y in rows if y is not None]
    curve = []
    for i in range(0, 101):
        t = i / 100
        tp = sum(1 for sc, y in labeled if sc >= t and y)
        fp = sum(1 for sc, y in labeled if sc >= t and not y)
        fn = sum(1 for sc, y in labeled if sc < t and y)
        tn = sum(1 for sc, y in labeled if sc < t and not y)
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / (tp + fn) if tp + fn else 1.0
        curve.append({"threshold": t, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(p, 3), "recall": round(r, 3),
                      "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "flagged": sum(1 for sc, _ in rows if sc >= t)})
    best = max(curve, key=lambda c: (c["f1"], -abs(c["threshold"] - 0.5)))
    hist = [{"bin": f"{b / 10:.1f}", "positive": 0, "negative": 0, "unlabeled": 0} for b in range(10)]
    for sc, y in rows:
        hist[min(int(sc * 10), 9)]["unlabeled" if y is None else ("positive" if y else "negative")] += 1
    return {"module": module, "threshold": th, "labeled": len(labeled), "positives": sum(1 for _, y in labeled if y),
            "total": len(rows), "curve": curve, "best_f1_threshold": best["threshold"], "histogram": hist}


# ------------------------------------------------------------------------------ raporty modułów
def _flagged(s, module: int):
    th = get_thresholds(s)
    return th, s.execute(_base().where(Finding.module == module, Finding.score >= th[module])
                         .order_by(Finding.score.desc())).all()


@app.get("/api/reports/m1")
def report_m1():
    """Firma inwestycyjna → podmioty reklamujące (zasady współpracy firm z reklamodawcami)."""
    with session_scope() as s:
        th, rows = _flagged(s, 1)
        firms: dict[str, dict] = {}
        for f, d in rows:
            firm = f.firm or {}
            g = firms.setdefault(firm.get("name", "?"), {"firm": firm, "ads": 0, "unlabeled": 0, "advertisers": {}})
            adv = f.advertiser or {}
            a = g["advertisers"].setdefault(adv.get("name") or d.domain, {
                "name": adv.get("name") or d.domain, "url": adv.get("url"), "platform": d.source_type, "ads": []})
            a["ads"].append({"finding_id": f.id, "url": d.url, "score": f.score, "risk_level": risk_level(f.score, th[1]),
                             "labeled": adv.get("is_labeled_ad"), "first_seen_at": iso(d.first_seen_at),
                             "last_seen_at": iso(d.last_seen_at), "availability": d.availability, "status": f.status,
                             "affiliate": bool((f.details or {}).get("affiliate_links"))})
            g["ads"] += 1
            g["unlabeled"] += adv.get("is_labeled_ad") is False
        out = []
        for name, g in sorted(firms.items(), key=lambda kv: -kv[1]["ads"]):
            out.append({**g, "name": name, "advertisers": sorted(g["advertisers"].values(), key=lambda a: -len(a["ads"]))})
        return out


@app.get("/api/reports/m2")
def report_m2():
    """Macierz: materiał × reguły 1–18 (status każdej reguły)."""
    with session_scope() as s:
        th = get_thresholds(s)
        rows = s.execute(_base().where(Finding.module == 2).order_by(Finding.score.desc())).all()
        items = [{"finding_id": f.id, "firm": (f.firm or {}).get("name"), "url": d.url, "title": d.title,
                  "score": f.score, "risk_level": risk_level(f.score, th[2]), "status": f.status,
                  "rules": {r["id"]: r["status"] for r in f.rules}} for f, d in rows]
    try:
        catalog = ai_client.rules()
    except Exception:
        catalog = []
    fail_counts = {}
    for it in items:
        for rid, st in it["rules"].items():
            if st == "fail" and it["risk_level"] != "low":
                fail_counts[rid] = fail_counts.get(rid, 0) + 1
    return {"rules": catalog, "items": items, "fail_counts": fail_counts}


@app.get("/api/reports/m3")
def report_m3():
    with session_scope() as s:
        th, rows = _flagged(s, 3)
        return [{"finding_id": f.id, "entity": f.entity, "category": f.category, "score": f.score,
                 "risk_level": risk_level(f.score, th[3]), "status": f.status, "url": d.url, "domain": d.domain,
                 "source_type": d.source_type, "definition": (f.details or {}).get("definition_art76", {}),
                 "on_warning_list": (f.details or {}).get("on_warning_list", False), "excerpt": f.excerpt[:400]}
                for f, d in rows]


@app.get("/api/export")
def export(module: list[int] = Query(default=[]), risk: list[str] = Query(default=["high", "medium"]),
           status: list[str] = Query(default=[]), fmt: str = "csv"):
    flt = _filters(module, [], risk, status, None, None, None)
    with session_scope() as s:
        th = get_thresholds(s)
        items = [finding_dict(f, d, th, full=True) for f, d in
                 s.execute(flt.apply(_base(), th).order_by(Finding.module, Finding.score.desc()))]
    if fmt == "json":
        return JSONResponse(items, headers={"Content-Disposition": "attachment; filename=scopeonmedia_raport.json"})
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "moduł", "kategoria", "score", "ryzyko", "status", "firma / podmiot", "kategoria rejestru",
                "podmiot reklamujący", "profil reklamującego", "oznaczona reklama", "URL", "źródło", "data publikacji",
                "pierwsze wykrycie", "ostatnio widziana", "dostępność", "NIP", "KRS", "e-mail", "naruszone reguły M2",
                "fragment treści"])
    for i in items:
        e = i.get("entity") or {}
        # csv_safe: treść ze stron nie może zaczynać się od =,+,-,@ (wykonałaby się jako formuła w Excelu)
        w.writerow([csv_safe(v) for v in [i["id"], i["module"], i["category"], i["score"], i["risk_level"], i["status"],
                    (i.get("firm") or {}).get("name"), (i.get("firm") or {}).get("category"),
                    (i.get("advertiser") or {}).get("name"), (i.get("advertiser") or {}).get("url"),
                    (i.get("advertiser") or {}).get("is_labeled_ad"), i["url"], i["source_type"], i.get("published_at"),
                    i["first_seen_at"], i["last_seen_at"], i["availability"], ", ".join(e.get("nip", [])),
                    ", ".join(e.get("krs", [])), ", ".join(e.get("emails", [])),
                    ", ".join(r["id"] for r in i.get("rules", []) if r["status"] == "fail"),
                    i["excerpt"].replace("\n", " ")[:600]]])
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=scopeonmedia_raport.csv"})


@app.get("/api/rules")
def rules_catalog():
    try:
        return ai_client.rules()
    except Exception:
        raise HTTPException(503, "silnik AI niedostępny") from None


@app.get("/api/documents/{doc_id}/screenshot/{viewport}")
def screenshot(doc_id: int, viewport: str):
    with session_scope() as s:
        d = s.get(Document, doc_id)
        key = (d.screenshots or {}).get(viewport) if d else None
    data = get_storage().get(key) if key else None
    if not data:
        raise HTTPException(404)
    return Response(data, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/findings/{fid}/evidence")
def evidence_package(fid: int):
    """Teczka dowodowa: ZIP z raportem PDF/HTML, zrzutami, źródłem, danymi JSON i sumami SHA-256."""
    from .evidence import build_package

    pkg = build_package(fid)
    if pkg is None:
        raise HTTPException(404)
    data, filename = pkg
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------------------ zadania i rejestr
class JobBody(BaseModel):
    kind: str = "all"           # all | web | urls | social | search | recheck | reanalyze | registry
    url: str | None = None
    urls: list[str] = Field(default_factory=list)
    platform: str | None = None
    query: str | None = None
    sources: list[str] = Field(default_factory=list)


def _require_fetchable(url: str) -> None:
    """Ochrona SSRF dla adresów wpisanych w dashboardzie: tylko http(s) i tylko adresy publiczne
    (lub hosty z IW_TRUSTED_LOCAL_HOSTS)."""
    if not fetch_allowed(url):
        raise HTTPException(400, f"Adres niedozwolony: {url[:200]} – dozwolone są publiczne adresy http(s); "
                                 "sieć lokalna i prywatna jest zablokowana")


@app.post("/api/jobs")
def enqueue(body: JobBody):
    from . import tasks

    seeds = tasks.load_seeds()
    queued: list[str] = []
    if body.kind in ("all", "web"):
        for seed in ([{"url": body.url}] if body.url else seeds.get("web", [])):
            if body.url:
                _require_fetchable(body.url)
            tasks.task_web(seed)
            queued.append(f"web: {seed['url']}")
    if body.kind == "urls" or (body.kind == "all" and seeds.get("urls")):
        for u in body.urls:
            _require_fetchable(u)
        urls = body.urls or seeds.get("urls", [])
        if urls:
            tasks.task_urls(urls)
            queued.append(f"urls: {len(urls)}")
    if body.kind in ("all", "social"):
        soc = seeds.get("social", {})
        for p in ([body.platform] if body.platform else soc.get("platforms", [])):
            if p not in ("facebook", "instagram", "tiktok"):
                raise HTTPException(400, "platforma: facebook | instagram | tiktok")
            for q in ([body.query] if body.query else soc.get("queries", [])):
                tasks.task_social(p, q)
                queued.append(f"{p}: {q}")
    if body.kind == "search" or (body.kind == "all" and seeds.get("search", {}).get("enabled")):
        for q in ([body.query] if body.query else seeds.get("search", {}).get("queries", [])):
            tasks.task_search(q)
            queued.append(f"search: {q}")
    if body.kind == "recheck":
        tasks.task_recheck()
        queued.append("recheck")
    if body.kind == "reanalyze":
        tasks.task_reanalyze()
        queued.append("reanalyze")
    if body.kind == "registry":
        tasks.task_registry(body.sources or None)
        queued.append("registry: " + ",".join(body.sources or config.REGISTRY_SOURCES))
    return {"queued": queued}


@app.get("/api/jobs")
def jobs(limit: int = 40):
    from .tasks import _job_dict

    with session_scope() as s:
        return [_job_dict(j) for j in s.scalars(select(CrawlJob).order_by(CrawlJob.id.desc()).limit(min(limit, 200)))]


@app.get("/api/registry")
def get_registry(q: str | None = None, category: str | None = None, limit: int = 200):
    with session_scope() as s:
        stmt = select(Entity).order_by(Entity.authorized, Entity.name)
        if category:
            stmt = stmt.where(Entity.category == category)
        if q:
            stmt = stmt.where(func.lower(Entity.name).like(f"%{q.lower()}%"))
        counts = dict(s.execute(select(Entity.category, func.count()).group_by(Entity.category)).all())
        return {"version": get_setting(s, "registry_version"), "counts": counts,
                "items": [{"id": e.id, "name": e.name, "category": e.category, "authorized": e.authorized,
                           "country": e.country, "domains": e.domains, "aliases": e.aliases, "source": e.source,
                           "license_date": e.license_date} for e in s.scalars(stmt.limit(min(limit, 1000)))]}


# ------------------------------------------------------------------------------ zdrowie
@app.get("/api/health")
def health():
    from .scraper import render
    from .tasks import huey

    with session_scope() as s:
        hb = (get_setting(s, "worker_heartbeat") or {}).get("at")
        reg_v = get_setting(s, "registry_version")
        n_ent = s.scalar(select(func.count()).select_from(Entity))
    age = (utcnow() - datetime.fromisoformat(hb)).total_seconds() if hb else None
    try:
        pending = huey.pending_count()
    except Exception:
        pending = None
    return {"ok": True, "version": __version__, "db": config.DATABASE_URL.split(":")[0], "storage": config.STORAGE_BACKEND,
            "queue": {"backend": config.QUEUE_BACKEND, "pending": pending},
            "worker": {"alive": age is not None and age < 150, "last_heartbeat_s": age},
            "render": render.available(), "registry": {"version": reg_v, "entities": n_ent},
            "ai_engine": ai_client.health()}


# ------------------------------------------------------------------------------ wewnętrzne (worker / ai-engine)
@app.get("/internal/registry")
def internal_registry(x_internal_token: str = Header(default="")):
    _check_internal(x_internal_token)
    return registry.snapshot()


class EventsBody(BaseModel):
    events: list[dict]


@app.post("/internal/events")
async def internal_events(body: EventsBody, x_internal_token: str = Header(default="")):
    _check_internal(x_internal_token)
    for e in body.events:
        if e.get("type") in {"alert", "finding_updated", "job", "registry"}:
            await sio.emit(e["type"], e.get("data"))
    return {"sent": len(body.events)}


@sio.event
async def connect(sid, environ, _auth=None):
    with session_scope() as s:
        await sio.emit("thresholds", get_thresholds(s), to=sid)


# ------------------------------------------------------------------------------ dane demonstracyjne (mock API)
@app.get("/demo/api/{platform}")
def social_mock(platform: str, q: str = ""):
    import json

    if platform not in {"facebook", "instagram", "tiktok"}:
        raise HTTPException(404)
    path = DEMO_DIR / "social" / f"{platform}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return {"data": data, "query": q, "paging": {}}


asgi = socketio.ASGIApp(sio, other_asgi_app=app)
