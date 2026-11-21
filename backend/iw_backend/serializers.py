"""Serializacja ujednoliconego obiektu wyniku dla API / WebSocket / eksportu."""
from __future__ import annotations

from datetime import datetime

from .db import Document, Finding, risk_level

MODULE_NAMES = {1: "Ekosystem zewnętrzny (finfluencerzy)", 2: "Zgodność i informacja o ryzyku",
                3: "Usługi nieautoryzowane (shadow advisory)"}


def iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def finding_dict(f: Finding, d: Document, thresholds: dict[int, float], full: bool = False) -> dict:
    out = {
        "id": f.id, "module": f.module, "module_name": MODULE_NAMES[f.module], "category": f.category,
        "score": f.score, "rule_score": f.rule_score, "llm_score": f.llm_score,
        "risk_level": risk_level(f.score, thresholds[f.module]), "threshold": thresholds[f.module],
        "status": f.status, "firm": f.firm, "advertiser": f.advertiser, "entity": f.entity,
        "excerpt": f.excerpt, "ground_truth": f.ground_truth, "analyst_note": f.analyst_note,
        "url": d.url, "fetched_url": d.fetched_url, "domain": d.domain, "source_type": d.source_type, "title": d.title,
        "availability": d.availability, "first_seen_at": iso(d.first_seen_at), "last_seen_at": iso(d.last_seen_at),
        "event_date": iso(f.event_date), "created_at": iso(f.created_at), "updated_at": iso(f.updated_at),
        "llm_status": (f.llm or {}).get("status"),
        "violations": sum(1 for r in f.rules if r.get("status") == "fail"),
    }
    if full:
        out.update({"reasons": f.reasons, "rules": f.rules, "details": f.details, "llm": f.llm,
                    "screenshots": sorted((d.screenshots or {}).keys()), "document_id": d.id,
                    "author": d.author, "author_url": d.author_url, "published_at": iso(d.published_at),
                    "near_duplicates": (d.meta or {}).get("near_duplicates", [])})
    return out
