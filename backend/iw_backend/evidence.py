"""Teczka dowodowa incydentu: ZIP z raportem (PDF + HTML), zrzutami ekranu, surowym źródłem, danymi JSON
i sumami SHA-256.

Zrzuty i źródło trafiają do Object Storage w chwili pobrania pod kluczem równym ich SHA-256
(storage.put_content_addressed). Zgodność skrótu pliku z kluczem potwierdza więc, że plik nie zmienił się
od chwili zebrania materiału – raport pokazuje to dla każdego pliku.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from html import escape

from sqlalchemy import select

from . import __version__
from .db import Finding, StatusHistory, get_thresholds, session_scope
from .security import safe_url
from .serializers import MODULE_NAMES, finding_dict, iso
from .storage import get_storage

log = logging.getLogger(__name__)

RISK = {"high": "wysokie", "medium": "średnie", "low": "poniżej progu"}
STATUS = {"new": "Nowy", "in_review": "W analizie", "confirmed": "Potwierdzony", "false_positive": "Fałszywy alarm",
          "closed": "Zamknięty"}
RULE = {"fail": "naruszona", "warn": "zastrzeżenie", "pass": "spełniona", "na": "nie dotyczy"}
VIEWPORTS = {"desktop": "komputer (1366 px)", "tablet": "tablet (820 px)", "phone": "telefon (390 px)"}
REGISTRY = {"dom_maklerski": "Dom maklerski", "bank_maklerski": "Bank (działalność maklerska)",
            "oddzial_zagranicznej_firmy": "Oddział zagranicznej firmy",
            "zagraniczna_firma_transgraniczna": "Firma zagraniczna (transgranicznie)",
            "ostrzezenie_knf": "Lista ostrzeżeń KNF", "brak_w_rejestrze": "Brak w rejestrze"}
MATCHED_BY = {"name": "nazwa w treści", "domain": "domena materiału", "domain_link": "domena w linku",
              "handle": "konto w mediach społecznościowych"}
CATEGORIES = {
    "reklama_finfluencer": "Reklama u finfluencera",
    "reklama_podmiot_trzeci": "Reklama u podmiotu trzeciego",
    "reklama_zagranicznej_firmy_inwestycyjnej": "Reklama zagranicznej firmy inwestycyjnej",
    "promocja_podmiotu_z_listy_ostrzezen_KNF": "Promocja podmiotu z listy ostrzeżeń KNF",
    "podmiot_z_listy_ostrzezen_KNF": "Podmiot z listy ostrzeżeń KNF",
    "doradztwo_inwestycyjne_bez_zezwolenia": "Doradztwo inwestycyjne bez zezwolenia",
    "zarzadzanie_portfelem_bez_zezwolenia": "Zarządzanie portfelem bez zezwolenia",
    "sygnaly_transakcyjne_bez_zezwolenia": "Sygnały transakcyjne bez zezwolenia",
    "poza_art_2_uoif_kryptoaktywa": "Poza art. 2 u.o.i.f. (kryptoaktywa)",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _key_matches(key: str | None, digest: str) -> bool:
    """Klucz obiektu ma postać prefix/ab/<sha256>.ext – skrót z chwili pobrania."""
    return bool(key) and key.rsplit("/", 1)[-1].split(".", 1)[0] == digest


def _fmt(d: str | None) -> str:
    if not d:
        return "—"
    return d.replace("T", " ")[:19] + " UTC"


def _e(v) -> str:
    return escape("—" if v in (None, "", [], {}) else str(v))


def _link(url: str | None) -> str:
    if url and safe_url(url):
        return f'<a href="{escape(url, quote=True)}">{escape(url)}</a>'
    return _e(url)


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "".join(f"<tr><th>{escape(k)}</th><td>{v}</td></tr>" for k, v in pairs)


CSS = """
@page { size: A4; margin: 16mm 14mm 18mm; }
* { box-sizing: border-box; }
body { font: 10pt/1.45 "Liberation Sans", Arial, Helvetica, sans-serif; color: #0a0a0a; margin: 0; }
.mono, code, .hash { font-family: "Liberation Mono", Consolas, monospace; }
header { border-bottom: 3px solid #0a0a0a; padding-bottom: 8px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-end; }
header .brand { font-weight: 700; font-size: 16pt; letter-spacing: -0.02em; }
header .brand i { display: inline-block; width: 12px; height: 12px; background: #e10600; margin-right: 8px; vertical-align: 1px; }
header .meta { text-align: right; font-size: 8.5pt; color: #555; }
h1 { font-size: 18pt; letter-spacing: -0.02em; margin: 0 0 4px; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: .06em; margin: 18px 0 6px; padding-top: 6px; border-top: 1px solid #0a0a0a; }
h2 span { color: #e10600; margin-right: 6px; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; vertical-align: top; padding: 4px 6px; border-bottom: 1px solid #d8d6d0; }
.kv th { width: 30%; font-weight: 600; color: #333; }
.grid th { font-size: 8pt; text-transform: uppercase; letter-spacing: .05em; color: #555; border-bottom: 1px solid #0a0a0a; }
.badge { display: inline-block; padding: 1px 6px; font-weight: 700; font-size: 8.5pt; white-space: nowrap; }
tr { break-inside: avoid; }
.badge.high, .badge.fail { background: #e10600; color: #fff; }
.badge.medium, .badge.warn { background: #f2b600; color: #0a0a0a; }
.badge.low, .badge.pass, .badge.na { border: 1px solid #0a0a0a; }
.excerpt { border-left: 3px solid #e10600; padding: 6px 10px; background: #f6f5f1; white-space: pre-wrap; }
.shot { margin: 8px 0 14px; break-inside: avoid; }
.shot img { display: block; max-width: 100%; max-height: 225mm; border: 1px solid #0a0a0a; }
.shot .cap { font-size: 8.5pt; color: #333; margin-bottom: 4px; }
.hash { font-size: 7.5pt; word-break: break-all; }
.ok { color: #0a7a2f; font-weight: 700; }
.bad { color: #e10600; font-weight: 700; }
.note { font-size: 8.5pt; color: #444; }
"""


def _report_html(f: dict, history: list[dict], files: list[dict], shots: list[dict], generated: str) -> str:
    risk = f["risk_level"]
    sections: list[str] = []
    no = 0

    def h2(title: str) -> str:
        """Nagłówek sekcji numerowany w chwili budowania – treść ze strony nie może wpłynąć na numerację."""
        nonlocal no
        no += 1
        return f'<h2><span>{no:02d}</span>{escape(title)}</h2>'

    sections.append(f"""{h2("Incydent")}<table class="kv">{_rows([
        ("Moduł", _e(f"M{f['module']} · {MODULE_NAMES[f['module']]}")),
        ("Kategoria", _e(CATEGORIES.get(f["category"], f["category"].replace("_", " ")))),
        ("Poziom ryzyka", f'<span class="badge {risk}">{escape(RISK.get(risk, risk))}</span> '
                          f'score {f["score"]:.3f} · próg {f["threshold"]:.2f}'),
        ("Reguły + embedding", _e(f"{f['rule_score']:.3f}")),
        ("Ocena LLM", _e(f"{f['llm_score']:.3f} ({(f.get('llm') or {}).get('model') or 'model lokalny'})"
                         if f.get("llm_score") is not None else None)),
        ("Status", _e(STATUS.get(f["status"], f["status"]))),
        ("Notatka analityka", _e(f.get("analyst_note"))),
    ])}</table>""")

    sections.append(f"""{h2("Materiał")}<table class="kv">{_rows([
        ("Adres (kanoniczny)", _link(f["url"])),
        ("Adres pobrania", _link(f["fetched_url"])),
        ("Źródło", _e(f"{f['source_type']} · {f['domain']}")),
        ("Tytuł", _e(f.get("title"))),
        ("Autor / reklamujący", _e(f.get("author") or (f.get("advertiser") or {}).get("name"))
                               + (f" · {_link(f['author_url'])}" if f.get("author_url") else "")),
        ("Publikacja", escape(_fmt(f.get("published_at")))),
        ("Pierwsze wykrycie", escape(_fmt(f.get("first_seen_at")))),
        ("Ostatnio widziany", escape(_fmt(f.get("last_seen_at")))),
        ("Dostępność", _e("online" if f.get("availability") == "online" else "usunięty ze źródła")),
    ])}</table>""")

    firm, ent = f.get("firm") or {}, f.get("entity") or {}
    firm_rows = [("Nazwa", f"<b>{_e(firm.get('name'))}</b>"),
                 ("Kategoria w rejestrze", _e(REGISTRY.get(firm.get("category"), firm.get("category")))),
                 ("Nr w rejestrze", _e(firm.get("register_id"))),
                 ("Kraj", _e(firm.get("country"))),
                 ("Zezwolenie", _e({True: "tak", False: "brak"}.get(firm.get("authorized")))),
                 ("Dopasowanie", _e(MATCHED_BY.get(firm.get("matched_by"), firm.get("matched_by"))))]
    for key, label in (("nip", "NIP"), ("krs", "KRS"), ("regon", "REGON"), ("emails", "E-mail"),
                       ("phones", "Telefon"), ("addresses", "Adres")):
        if ent.get(key):
            firm_rows.append((label, _e(", ".join(map(str, ent[key])))))
    sections.append(h2("Podmiot" if f["module"] == 3 else "Firma inwestycyjna")
                    + f'<table class="kv">{_rows(firm_rows)}</table>')

    reasons = "".join(f"<tr><td>{_e(r.get('label') or r.get('rule'))}</td><td>{_e(r.get('evidence'))}</td>"
                      f"<td class='mono'>{_e(r.get('weight'))}</td></tr>" for r in f.get("reasons") or [])
    sections.append(h2("Uzasadnienie (sygnały z dowodem)")
                    + (f'<table class="grid"><tr><th>Sygnał</th><th>Dowód z treści</th><th>Waga</th></tr>{reasons}</table>'
                       if reasons else '<p class="note">Brak sygnałów.</p>'))

    if f.get("rules"):
        rules = "".join(
            f"<tr><td class='mono'>{_e(r.get('id'))}</td><td>{_e(r.get('name'))}</td>"
            f"<td><span class='badge {escape(r.get('status', ''))}'>{escape(RULE.get(r.get('status'), r.get('status') or '—'))}</span></td>"
            f"<td>{_e(r.get('evidence'))}</td><td class='note'>{_e(r.get('basis'))}</td></tr>" for r in f["rules"])
        sections.append(h2("Kryteria informacji o ryzyku") + '<table class="grid"><tr><th>Nr</th>'
                        f'<th>Reguła</th><th>Wynik</th><th>Dowód</th><th>Podstawa</th></tr>{rules}</table>')

    sections.append(h2("Fragment materiału") + f'<div class="excerpt">{_e(f.get("excerpt"))}</div>')

    if shots:
        imgs = "".join(
            f'<div class="shot"><div class="cap"><b>{escape(VIEWPORTS.get(s["viewport"], s["viewport"]))}</b> · '
            f'<span class="hash">SHA-256 {s["sha256"]}</span></div>'
            f'<img src="data:image/png;base64,{s["b64"]}" alt="zrzut {escape(s["viewport"])}"></div>' for s in shots)
        # nagłówek w pierwszym bloku zrzutu – nie zostaje sam na dole strony
        sections.append(imgs.replace('<div class="shot">', '<div class="shot">' + h2("Zrzuty ekranu (z chwili pobrania)"), 1))

    if history:
        hist = "".join(f"<tr><td>{escape(_fmt(h['at']))}</td><td>{_e(STATUS.get(h['old'], h['old']))} → "
                       f"<b>{_e(STATUS.get(h['new'], h['new']))}</b></td><td>{_e(h.get('note'))}</td></tr>" for h in history)
        sections.append(h2("Historia statusu") + f'<table class="grid"><tr><th>Data</th><th>Zmiana</th>'
                        f'<th>Notatka</th></tr>{hist}</table>')

    integ = "".join(
        f"<tr><td class='mono'>{escape(x['path'])}</td><td class='hash'>{x['sha256']}</td><td>"
        + ("<span class='ok'>zgodny z zapisem z chwili pobrania</span>" if x.get("captured") is True
           else "<span class='bad'>niezgodny z zapisem</span>" if x.get("captured") is False else "—")
        + "</td></tr>" for x in files)
    sections.append(f"""{h2("Integralność plików")}
<table class="grid"><tr><th>Plik w teczce</th><th>SHA-256</th><th>Pochodzenie</th></tr>{integ}</table>
<p class="note">Zrzuty ekranu i źródło są zapisywane w chwili pobrania pod kluczem równym ich skrótowi SHA-256 –
zgodność skrótu z kluczem potwierdza, że plik nie zmienił się od chwili zebrania materiału. Skróty wszystkich plików
(także tego raportu) są w pliku <code>SHA256SUMS</code>; sprawdzenie: <code>sha256sum -c SHA256SUMS</code> (Linux)
albo <code>Get-FileHash -Algorithm SHA256</code> (Windows).</p>""")

    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<title>Teczka dowodowa – incydent #{f['id']}</title><style>{CSS}</style></head><body>
<header><div class="brand"><i></i>ScopeOnMedia</div>
<div class="meta">Teczka dowodowa · incydent #{f['id']}<br>wygenerowano {escape(generated)} · ScopeOnMedia {escape(__version__)}</div></header>
<h1>{_e(CATEGORIES.get(f["category"], f["category"].replace("_", " ")))}</h1>
<div class="note">{_link(f["url"])}</div>
{''.join(sections)}
</body></html>"""


def _html_to_pdf(html_doc: str) -> bytes | None:
    """PDF przez Chromium z Playwright (ten sam co do renderowania stron). Bez JS i bez sieci –
    raport ma wszystko w sobie. Brak Chromium = teczka bez PDF (zostaje raport HTML)."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(java_script_enabled=False)
                page.route("**/*", lambda route: route.abort())
                page.set_content(html_doc, wait_until="load")
                return page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
            finally:
                browser.close()
    except Exception:
        log.warning("PDF teczki dowodowej niedostępny – w teczce zostaje raport HTML", exc_info=True)
        return None


def build_package(fid: int) -> tuple[bytes, str] | None:
    """Zwraca (zip, nazwa pliku) albo None, gdy incydent nie istnieje."""
    with session_scope() as s:
        f = s.get(Finding, fid)
        if not f:
            return None
        d = f.document
        data = finding_dict(f, d, get_thresholds(s), full=True)
        text = d.content.text if d.content else ""
        history = [{"old": h.old_status, "new": h.new_status, "note": h.note, "at": iso(h.changed_at)}
                   for h in s.scalars(select(StatusHistory).where(StatusHistory.finding_id == fid)
                                      .order_by(StatusHistory.changed_at))]
        shot_keys = dict(sorted((d.screenshots or {}).items()))
        raw_key = d.raw_key

    now = datetime.now(timezone.utc)
    generated = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    storage = get_storage()
    files: dict[str, bytes] = {}
    integrity: list[dict] = []
    shots: list[dict] = []

    for vp, key in shot_keys.items():
        png = storage.get(key)
        if not png:
            continue
        path, digest = f"zrzuty/{vp}.png", _sha256(png)
        files[path] = png
        integrity.append({"path": path, "sha256": digest, "captured": _key_matches(key, digest)})
        shots.append({"viewport": vp, "sha256": digest, "b64": base64.b64encode(png).decode()})
    raw = storage.get(raw_key) if raw_key else None
    if raw:
        path = "zrodlo." + raw_key.rsplit(".", 1)[-1]
        files[path] = raw
        integrity.append({"path": path, "sha256": _sha256(raw), "captured": _key_matches(raw_key, _sha256(raw))})

    data.pop("text", None)
    data["status_history"] = history
    data["package"] = {"generated_at": now.isoformat(), "generator": f"ScopeOnMedia {__version__}"}
    files["dane.json"] = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    files["tekst.txt"] = text.encode("utf-8")
    for path in ("dane.json", "tekst.txt"):
        integrity.append({"path": path, "sha256": _sha256(files[path]), "captured": None})

    html_doc = _report_html(data, history, integrity, shots, generated)
    files["raport.html"] = html_doc.encode("utf-8")
    pdf = _html_to_pdf(html_doc)
    if pdf:
        files["raport.pdf"] = pdf
    files["SHA256SUMS"] = "".join(f"{_sha256(b)}  {p}\n" for p, b in sorted(files.items())).encode()

    folder = f"teczka_incydent_{fid}_{now:%Y%m%d-%H%M}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, blob in sorted(files.items()):
            z.writestr(f"{folder}/{path}", blob)
    return buf.getvalue(), f"{folder}.zip"
