"""Kopia rejestru podmiotów (pobierana z backendu, odświeżana przy zmianie wersji) i dopasowanie w treściach.

Kategorie zgodne z załącznikiem do Tematu 1/2 (definicja firmy inwestycyjnej) i rejestrami KNF:
  dom_maklerski · bank_maklerski · oddzial_zagranicznej_firmy · zagraniczna_firma_transgraniczna
  ostrzezenie_knf (Lista ostrzeżeń publicznych KNF – podmiot BEZ zezwolenia)
  agent_firmy_inwestycyjnej (rejestr agentów KNF – działa w imieniu firmy, wyłączony z M3)
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from . import config
from .text import fold

log = logging.getLogger(__name__)

INVESTMENT_FIRM_CATEGORIES = {"dom_maklerski", "bank_maklerski", "oddzial_zagranicznej_firmy",
                              "zagraniczna_firma_transgraniczna"}
AGENT_CATEGORY = "agent_firmy_inwestycyjnej"
GENERIC = {"dom", "maklerski", "maklerskie", "biuro", "bank", "polska", "polski", "spolka", "akcyjna", "investment",
           "investments", "capital", "invest", "securities", "management", "asset", "assets", "markets", "market",
           "trade", "trading", "finance", "financial", "group", "global", "europe", "oddzial", "limited", "inwestycyjny",
           "inwestycje", "brokers", "broker", "partners", "company", "holding", "services", "fund", "funds"}


@dataclass
class Entity:
    id: int
    name: str
    category: str
    authorized: bool
    country: str
    register_id: str | None
    domains: list[str]
    handles: list[str]
    patterns: list[tuple[re.Pattern, bool]]          # (wzorzec, czy na tekście oryginalnym – akronimy)
    distinct_tokens: list[str]

    @property
    def is_investment_firm(self) -> bool:
        return self.authorized and self.category in INVESTMENT_FIRM_CATEGORIES

    @property
    def is_registered_agent(self) -> bool:
        """Agent firmy inwestycyjnej z rejestru KNF – działa legalnie w imieniu firmy, więc nie jest „shadow advisory”."""
        return self.authorized and self.category == AGENT_CATEGORY


@dataclass
class Match:
    entity: Entity
    by: str            # name | alias | domain_link | handle
    evidence: str


def _inflect(word: str) -> str:
    """Wzorzec tolerujący polską fleksję: „Nadwiślański” → nadwislansk(i|iego|im…), „Vistula” → vistul(a|i|e…)."""
    if len(word) < 4 or not word.isalpha():
        return re.escape(word)
    if re.search(r"(ski|cki|dzki)$", word):
        return re.escape(word[:-1]) + r"[a-z]{0,3}"
    if word[-1] in "aeiouy":
        return re.escape(word[:-1]) + r"[a-z]{0,3}"
    return re.escape(word) + r"(?:[aeiouy][a-z]{0,2})?"


def _compile(names: list[str]) -> list[tuple[re.Pattern, bool]]:
    out = []
    for n in {n.strip() for n in names if n and n.strip()}:
        compact = n.replace(" ", "")
        if len(compact) < 5 and compact.isupper():
            out.append((re.compile(r"(?<![\w])" + re.escape(n) + r"(?![\w])"), True))
        elif len(compact) >= 4:
            body = r"\s+".join(_inflect(w) for w in fold(n).split())
            out.append((re.compile(r"(?<![\w])" + body + r"(?![\w])"), False))
    return out


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def domain_matches(domain: str, entity_domains: list[str]) -> bool:
    domain = domain.lower().removeprefix("www.")
    return any(domain == d or domain.endswith("." + d) for d in entity_domains)


class Registry:
    def __init__(self):
        self.version: str | None = None
        self.entities: list[Entity] = []
        self._lock = threading.Lock()

    def load(self, payload: dict) -> None:
        ents = []
        for e in payload.get("entities", []):
            names = [e["name"], *e.get("aliases", []), *e.get("former_names", [])]
            distinct = [t for t in re.findall(r"[a-z0-9]{4,}", fold(e["name"])) if t not in GENERIC]
            ents.append(Entity(e["id"], e["name"], e["category"], e["authorized"], e.get("country", "PL"),
                               e.get("register_id"), [d.lower() for d in e.get("domains", [])],
                               [h.lower() for h in e.get("social_handles", [])], _compile(names), distinct))
        with self._lock:
            self.entities, self.version = ents, payload.get("version")

    def ensure(self, version: str | None) -> None:
        if version and version == self.version and self.entities:
            return
        try:
            r = httpx.get(f"{config.BACKEND_URL}/internal/registry", timeout=30,
                          headers={"X-Internal-Token": config.INTERNAL_TOKEN})
            r.raise_for_status()
            self.load(r.json())
            log.info("rejestr załadowany: %d podmiotów (wersja %s)", len(self.entities), self.version)
        except Exception as exc:
            log.warning("nie udało się pobrać rejestru z backendu: %s", exc)

    # ----------------------------------------------------------------- dopasowania
    def owner_of(self, domain: str, author: str | None, author_url: str | None) -> tuple[Entity | None, str | None]:
        """Do kogo należy kanał publikacji (domena / profil social media)."""
        for e in self.entities:
            if e.domains and domain_matches(domain, e.domains):
                return e, "domain"
        handle_src = " ".join(filter(None, [author, author_url])).lower()
        for e in self.entities:
            for h in e.handles:
                if h and (h in handle_src or h.lstrip("@") in handle_src):
                    return e, "social_handle"
        if author:
            af = fold(author)
            for e in self.entities:
                if len(af) <= len(fold(e.name)) + 8 and any(
                        (p.search(author) if on_raw else p.search(af)) for p, on_raw in e.patterns):
                    return e, "author_name"
        # heurystyka dla podmiotów z rejestru KNF bez znanej domeny: charakterystyczny człon nazwy w domenie
        label = domain.split(".")[-2] if domain.count(".") >= 1 else domain
        for e in self.entities:
            if not e.domains and e.distinct_tokens and any(t in label for t in e.distinct_tokens if len(t) >= 5):
                return e, "domain_heuristic"
        return None, None

    def find(self, text: str, folded: str, links: list[str]) -> list[Match]:
        out: dict[int, Match] = {}
        for e in self.entities:
            for p, on_raw in e.patterns:
                m = p.search(text) if on_raw else p.search(folded)
                if m:
                    out[e.id] = Match(e, "name", m.group(0))
                    break
            if e.id in out:
                continue
            for link in links:
                h = host_of(link)
                if h and e.domains and domain_matches(h, e.domains):
                    out[e.id] = Match(e, "domain_link", link)
                    break
            if e.id in out:
                continue
            for h in e.handles:
                if h and h in folded:
                    out[e.id] = Match(e, "handle", h)
                    break
        return list(out.values())


registry = Registry()
