"""Import Rejestru Firm Inwestycyjnych KNF (strony wskazane w załączniku do Tematu 1/2).

Każdy podmiot na stronie KNF to osobna tabela <th>pole</th><td>wartość</td>; listy są stronicowane (?page=N).
Poprzednie nazwy podmiotu są przekreślone (<strike>) – zapisujemy je jako former_names.
Rejestr nie podaje marek ani domen, więc uzupełnia je brands.json (XTB, eToro, mBank… → nazwa rejestrowa).
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from ..scraper.http import Fetcher
from . import upsert

log = logging.getLogger(__name__)
BRANDS_FILE = Path(__file__).parent / "brands.json"
PAGE_ATTEMPTS = 4          # serwer KNF potrafi zerwać połączenie bez odpowiedzi – ponawiamy z rosnącą przerwą
BASE ="https://www.knf.gov.pl/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych/"
SOURCES = {
    "domy_maklerskie": "dom_maklerski",
    "Banki_prowadzace_dzialalnosc_maklerska": "bank_maklerski",
    "notyfikowane_firmy_inwestycyjne_oddzialy": "oddzial_zagranicznej_firmy",
    "notyfikowane_zagraniczne_firmy_inwestycyjne": "zagraniczna_firma_transgraniczna",
}
# agenci firm inwestycyjnych działają legalnie w imieniu firmy – M3 (shadow advisory) ich wyklucza
AGENT_CATEGORY = "agent_firmy_inwestycyjnej"
AGENT_SOURCES = ("agenci_firm_inwestycyjnych_osoby_fizyczne", "agenci_firm_inwestycyjnych_osoby_prawne")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_page(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for table in soup.find_all("table"):
        fields: dict[str, object] = {}
        for tr in table.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            key = _clean(th.get_text(" ", strip=True)).lower()
            if key.startswith("nazwa"):
                former = [_clean(x.get_text(" ", strip=True)) for x in td.find_all("strike")]
                for x in td.find_all("strike"):
                    x.decompose()
                parts = [_clean(p) for p in td.get_text("|", strip=True).split("|") if _clean(p)]
                fields["name"] = parts[0] if parts else ""
                fields["aliases"] = parts[1:]
                fields["former_names"] = former
            else:
                fields[key] = _clean(td.get_text(", ", strip=True))
        if not fields.get("name"):
            continue
        out.append({
            "name": fields["name"], "aliases": fields.get("aliases", []), "former_names": fields.get("former_names", []),
            "category": category, "authorized": True,
            "country": "PL" if category in {"dom_maklerski", "bank_maklerski"} else str(fields.get("państwo macierzyste", "")),
            "address": str(fields.get("dane teleadresowe") or fields.get("adres siedziby") or "")[:400] or None,
            "license_date": str(fields.get("data zezwolenia") or fields.get("data wpływu zawiadomienia") or "")[:20] or None,
            "scope": str(fields.get("zakres działalności") or fields.get("usługi inwestycyjne (a)") or "")[:200] or None,
            "register_id": f"KNF:{category}:{fields['name'][:60]}",
        })
    return out


def load_brands() -> dict[str, dict]:
    """Nazwa rejestrowa (casefold) → {aliases, domains, social_handles} z brands.json."""
    data = json.loads(BRANDS_FILE.read_text(encoding="utf-8"))
    return {n.casefold(): b for b in data["brands"] for n in b["register_names"]}


def apply_brands(rows: list[dict], brands: dict[str, dict] | None = None) -> list[dict]:
    """Dopisuje marki i domeny do podmiotów z rejestru (bez duplikatów, z zachowaniem aliasów z KNF)."""
    brands = load_brands() if brands is None else brands
    for r in rows:
        b = brands.get(r["name"].casefold())
        if not b:
            continue
        for key in ("aliases", "domains", "social_handles"):
            r[key] = list(dict.fromkeys([*r.get(key, []), *b.get(key, [])]))
    return rows


def _get_page(fetcher: Fetcher, url: str):
    for attempt in range(PAGE_ATTEMPTS):
        try:
            return fetcher.get(url)
        except Exception as exc:
            log.warning("KNF %s – próba %d/%d nieudana: %s", url, attempt + 1, PAGE_ATTEMPTS, exc)
            time.sleep(2 + 3 * attempt)
    return None


def parse_agents(html: str) -> list[dict]:
    """Rejestr agentów firm inwestycyjnych (osoby fizyczne i prawne) – inne pola niż w rejestrze firm:
    nazwa agenta to „Imię i nazwisko agenta…” albo „Nazwa”, a „Nazwa firmy inwestycyjnej…” to firma, dla której działa."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for table in soup.find_all("table"):
        fields: dict[str, str] = {}
        for tr in table.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                fields[_clean(th.get_text(" ", strip=True)).lower()] = _clean(td.get_text(" ", strip=True))
        name = next((v for k, v in fields.items() if k.startswith("imię i nazwisko") or k == "nazwa"), "")
        principal = next((v for k, v in fields.items() if k.startswith("nazwa firmy inwestycyjnej")), "")
        if not name:
            continue
        out.append({
            "name": name, "aliases": [], "category": AGENT_CATEGORY, "authorized": True, "country": "PL",
            "address": fields.get("dane teleadresowe")[:400] if fields.get("dane teleadresowe") else None,
            "license_date": next((v[:20] for k, v in fields.items() if k.startswith("data")), None),
            "scope": f"agent: {principal}"[:200] if principal else "agent firmy inwestycyjnej",
            "register_id": f"KNF:agent:{name[:60]}",
        })
    return out


def _import_list(fetcher: Fetcher, path: str, category: str, parse, max_pages: int, delay_s: float) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        url = BASE + path + (f"?page={page}" if page > 1 else "")
        r = _get_page(fetcher, url)
        if r is None or r.status_code != 200:   # zapisujemy to, co udało się pobrać (upsert nie usuwa starych wpisów)
            log.warning("KNF %s: import przerwany na stronie %d", category, page)
            break
        batch = [x for x in parse(r.text) if x["name"] not in seen]
        if not batch:
            break
        seen.update(x["name"] for x in batch)
        rows += batch
        if f"page={page + 1}" not in r.text:
            break
        time.sleep(delay_s)
    return rows


def import_knf(max_pages: int = 60, delay_s: float = 0.6, fetcher: Fetcher | None = None) -> dict[str, int]:
    fetcher = fetcher or Fetcher(delay_s=delay_s)
    brands = load_brands()
    counts: dict[str, int] = {}
    for path, category in SOURCES.items():
        rows = _import_list(fetcher, path, category, lambda html, c=category: parse_page(html, c), max_pages, delay_s)
        counts[category] = upsert(apply_brands(rows, brands), f"knf:{path}") if rows else 0
        log.info("KNF %s: %d podmiotów", category, counts[category])
    agents: list[dict] = []
    for path in AGENT_SOURCES:
        agents += _import_list(fetcher, path, AGENT_CATEGORY, parse_agents, max_pages, delay_s)
    counts[AGENT_CATEGORY] = upsert(agents, "knf:agenci") if agents else 0
    log.info("KNF agenci: %d", counts[AGENT_CATEGORY])
    return counts
