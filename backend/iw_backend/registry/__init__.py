"""Rejestr podmiotów: import (demo / KNF), wersjonowanie i udostępnianie silnikowi AI."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import select

from ..db import Entity, get_setting, put_setting, session_scope

DEMO_FILE = Path(__file__).parent / "demo_registry.json"
CATEGORIES = {
    "dom_maklerski": "Dom maklerski",
    "bank_maklerski": "Bank prowadzący działalność maklerską",
    "oddzial_zagranicznej_firmy": "Oddział zagranicznej firmy inwestycyjnej",
    "zagraniczna_firma_transgraniczna": "Zagraniczna firma inwestycyjna (bez oddziału)",
    "ostrzezenie_knf": "Lista ostrzeżeń publicznych KNF",
}
LEGAL_FORMS = re.compile(r"\b(s\.?\s?a\.?|sp\.?\s?z\s?o\.?\s?o\.?|spółka akcyjna|spółka z ograniczoną odpowiedzialnością|"
                         r"sp\.?\s?k\.?|ltd\.?|limited|plc|gmbh|ag|se|n\.?v\.?|b\.?v\.?|s\.?a\.?r\.?l\.?|a\.?s\.?|"
                         r"oddział w polsce|branch in poland|dom maklerski|dom inwestycyjny|biuro maklerskie)\b", re.I)
GENERIC = {"bank", "polska", "polski", "investment", "investments", "capital", "invest", "securities", "management",
           "asset", "markets", "trade", "trading", "finance", "financial", "group", "global", "europe", "partners",
           "company", "holding", "services", "brokers", "broker", "the"}


def derive_aliases(name: str) -> list[str]:
    """Nazwa handlowa z nazwy rejestrowej: bez formy prawnej i członów typu „Dom Maklerski”."""
    core = re.sub(r"\s+", " ", LEGAL_FORMS.sub(" ", name)).strip(" ,.-")
    out = []
    if core and core.lower() != name.lower() and len(core.replace(" ", "")) >= 3 and core.lower() not in GENERIC:
        out.append(core)
    return out


def upsert(rows: list[dict], source: str) -> int:
    n = 0
    with session_scope() as s:
        for r in rows:
            e = s.scalar(select(Entity).where(Entity.name == r["name"], Entity.category == r["category"]))
            if e is None:
                e = Entity(name=r["name"], category=r["category"])
                s.add(e)
            aliases = list(dict.fromkeys([*r.get("aliases", []), *derive_aliases(r["name"])]))
            e.aliases = aliases
            e.former_names = r.get("former_names", [])
            e.domains = [d.lower() for d in r.get("domains", [])] or e.domains or []
            e.social_handles = [h.lower() for h in r.get("social_handles", [])] or e.social_handles or []
            e.authorized = bool(r.get("authorized", True))
            e.country = r.get("country", "PL")
            e.register_id = r.get("register_id")
            e.address = r.get("address")
            e.license_date = r.get("license_date")
            e.scope = r.get("scope")
            e.source = source
            n += 1
        s.flush()
        _bump_version(s)
    return n


def _bump_version(s) -> str:
    rows = [(e.id, e.name, e.category, e.authorized, tuple(e.aliases), tuple(e.domains), tuple(e.social_handles))
            for e in s.scalars(select(Entity).order_by(Entity.id))]
    v = hashlib.sha1(json.dumps(rows, default=str).encode()).hexdigest()[:12]
    put_setting(s, "registry_version", v)
    return v


def load_demo() -> int:
    return upsert(json.loads(DEMO_FILE.read_text(encoding="utf-8"))["entities"], "demo")


def snapshot() -> dict:
    with session_scope() as s:
        return {"version": get_setting(s, "registry_version"),
                "entities": [{"id": e.id, "name": e.name, "aliases": e.aliases, "former_names": e.former_names,
                              "domains": e.domains, "social_handles": e.social_handles, "category": e.category,
                              "authorized": e.authorized, "country": e.country, "register_id": e.register_id}
                             for e in s.scalars(select(Entity))]}


def version() -> str | None:
    with session_scope() as s:
        return get_setting(s, "registry_version")
