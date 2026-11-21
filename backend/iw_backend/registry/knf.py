"""Import Rejestru Firm Inwestycyjnych KNF (strony wskazane w załączniku do Tematu 1/2).

Każdy podmiot na stronie KNF to osobna tabela <th>pole</th><td>wartość</td>; listy są stronicowane (?page=N).
Poprzednie nazwy podmiotu są przekreślone (<strike>) – zapisujemy je jako former_names.
"""
from __future__ import annotations

import logging
import re
import time

from bs4 import BeautifulSoup

from ..scraper.http import Fetcher
from . import upsert

log = logging.getLogger(__name__)
BASE = "https://www.knf.gov.pl/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych/"
SOURCES = {
    "domy_maklerskie": "dom_maklerski",
    "Banki_prowadzace_dzialalnosc_maklerska": "bank_maklerski",
    "notyfikowane_firmy_inwestycyjne_oddzialy": "oddzial_zagranicznej_firmy",
    "notyfikowane_zagraniczne_firmy_inwestycyjne": "zagraniczna_firma_transgraniczna",
}


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


def import_knf(max_pages: int = 60, delay_s: float = 0.6, fetcher: Fetcher | None = None) -> dict[str, int]:
    fetcher = fetcher or Fetcher(delay_s=delay_s)
    counts: dict[str, int] = {}
    for path, category in SOURCES.items():
        rows: list[dict] = []
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            url = BASE + path + (f"?page={page}" if page > 1 else "")
            r = fetcher.get(url)
            if r.status_code != 200:
                break
            batch = [x for x in parse_page(r.text, category) if x["name"] not in seen]
            if not batch:
                break
            seen.update(x["name"] for x in batch)
            rows += batch
            if f"page={page + 1}" not in r.text:
                break
            time.sleep(delay_s)
        counts[category] = upsert(rows, f"knf:{path}") if rows else 0
        log.info("KNF %s: %d podmiotów", category, counts[category])
    return counts
