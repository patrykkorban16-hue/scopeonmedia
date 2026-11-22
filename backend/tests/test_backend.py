import json

from fastapi.testclient import TestClient

from iw_backend.db import high_cut, risk_level
from iw_backend.registry import derive_aliases
from iw_backend.registry.knf import parse_page
from iw_backend.scraper.extract import extract_html, extract_social_item, platform_of

KNF_SAMPLE = """
<table class="rounded-default"><tbody>
<tr><th scope="row">Nazwa</th><td><span>CERES DOM INWESTYCYJNY S.A.<br/><strike>EFIX DOM MAKLERSKI S.A.</strike></span></td></tr>
<tr><th scope="row">Dane Teleadresowe</th><td><ul><li><span>Plac Bankowy 1</span></li><li><span>00-139 Warszawa</span></li></ul></td></tr>
<tr><th scope="row">Data zezwolenia</th><td><span>08-02-2011</span></td></tr>
<tr><th scope="row">Zakres działalności</th><td><span>1, 4, 5</span></td></tr>
</tbody></table>
<table><tbody><tr><th>Nazwa</th><td><span>ALIOR BANK S.A.</span><br/><span>Biuro Maklerskie ALIOR Bank</span></td></tr></tbody></table>
"""


def test_knf_register_parser():
    rows = parse_page(KNF_SAMPLE, "dom_maklerski")
    assert rows[0]["name"] == "CERES DOM INWESTYCYJNY S.A."
    assert rows[0]["former_names"] == ["EFIX DOM MAKLERSKI S.A."]
    assert "Warszawa" in rows[0]["address"] and rows[0]["license_date"] == "08-02-2011"
    assert rows[1]["aliases"] == ["Biuro Maklerskie ALIOR Bank"]


def test_derive_aliases_strips_legal_form():
    assert derive_aliases("CERES DOM INWESTYCYJNY S.A.") == ["CERES"]
    assert derive_aliases("Vistula Dom Maklerski S.A.") == ["Vistula"]
    assert derive_aliases("GoldStar Capital Partners") == []


def test_extract_html_canonical_jsonld_and_labels():
    html = """<html lang="pl"><head><link rel="canonical" href="https://www.youtube.com/watch?v=X1">
    <meta name="robots" content="noindex, follow"><meta name="iw-ground-truth" content='{"1": true}'>
    <script type="application/ld+json">{"@type":"VideoObject","author":{"name":"Kanał","url":"https://www.youtube.com/@k"},
    "uploadDate":"2026-11-10","interactionStatistic":[{"interactionType":"https://schema.org/WatchAction","userInteractionCount":64000}]}</script>
    </head><body><a href="/x?ref=1">a</a></body></html>"""
    d = extract_html(html, "http://127.0.0.1:8000/demo/sites/v.html")
    assert d["url"] == "https://www.youtube.com/watch?v=X1" and d["source_type"] == "youtube"
    assert d["author"] == "Kanał" and d["author_url"] == "https://www.youtube.com/@k"
    assert d["published_at"].year == 2026 and d["metrics"]["WatchAction"] == 64000
    assert d["noindex"] and d["ground_truth"] == {"1": True}
    assert d["links"] == ["http://127.0.0.1:8000/x?ref=1"]


def test_social_item_normalization():
    d = extract_social_item({"platform": "tiktok", "url": "https://www.tiktok.com/@a/video/1", "text": "Kod ABC",
                             "hashtags": ["#ad"], "published_at": "2026-10-06"})
    assert d["source_type"] == "tiktok" and "#ad" in d["text"] and platform_of("https://m.facebook.com/x") == "facebook"


def test_internal_token_fail_fast(monkeypatch):
    import pytest

    from iw_backend import config

    for bad in ("", "change-me-long-random-string", "za-krotki"):
        monkeypatch.setattr(config, "INTERNAL_TOKEN", bad)
        with pytest.raises(RuntimeError):
            config.require_internal_token()
    monkeypatch.setattr(config, "INTERNAL_TOKEN", "x" * 32)
    config.require_internal_token()


def test_risk_levels_follow_threshold():
    assert risk_level(0.4, 0.5) == "low"
    assert risk_level(0.6, 0.5) == "medium"
    assert risk_level(0.8, 0.5) == "high" and high_cut(0.5) == 0.75


def test_api_thresholds_calibration_and_internal_auth():
    from iw_backend.api import app

    with TestClient(app) as c:
        assert c.put("/api/thresholds/2", json={"value": 0.42}).json()["2"] == 0.42
        assert c.put("/api/thresholds/2", json={"value": 1.5}).status_code == 422
        cal = c.get("/api/calibration/2").json()
        assert len(cal["curve"]) == 101 and cal["threshold"] == 0.42
        assert c.get("/internal/registry").status_code == 403
        reg = c.get("/internal/registry", headers={"X-Internal-Token": "test-token-0123456789abcdef0123"}).json()
        assert len(reg["entities"]) == 6 and reg["version"]
        assert c.patch("/api/findings/999", json={"status": "confirmed"}).status_code == 404
        assert c.patch("/api/findings/999", json={"status": "zly"}).status_code == 400
        assert c.get("/api/findings?risk=high&module=1").json()["total"] == 0
        assert json.loads(c.get("/demo/api/tiktok").text)["data"] is not None
        # ochrona SSRF: adresu metadanych chmury / sieci lokalnej nie da się zlecić do pobrania
        for bad in ("http://169.254.169.254/latest/meta-data", "http://127.0.0.1:11434/api/tags", "javascript:alert(1)"):
            assert c.post("/api/jobs", json={"kind": "web", "url": bad}).status_code == 400
        assert c.get("/api/export?fmt=csv").status_code == 200


def test_url_safety_ssrf_and_csv():
    from iw_backend.security import csv_safe, fetch_allowed, safe_url

    assert safe_url("javascript:alert(1)") is None and safe_url("data:text/html,x") is None
    assert safe_url("https://firma.test/a") == "https://firma.test/a"
    for bad in ("http://127.0.0.1:9999/", "http://10.0.0.5/", "http://169.254.169.254/", "http://[::1]/", "ftp://1.1.1.1/"):
        assert not fetch_allowed(bad), bad
    assert fetch_allowed("http://127.0.0.1:8000/demo/sites/index.html")      # zaufany host demo
    assert fetch_allowed("https://1.1.1.1/")
    assert csv_safe("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")" and csv_safe("+48 123") == "'+48 123"
    assert csv_safe("Zwykły tekst") == "Zwykły tekst" and csv_safe(0.5) == 0.5


def test_foreign_page_cannot_hijack_url_or_labels():
    html = """<html><head><link rel="canonical" href="https://vistula-dm.test/rachunek-maklerski">
    <meta name="iw-ground-truth" content='{"2": false}'>
    <script type="application/ld+json">{"author":{"name":"x","url":"javascript:alert(2)"}}</script></head>
    <body><a href="javascript:alert(3)">a</a><a href="https://ok.test/b">b</a></body></html>"""
    d = extract_html(html, "https://zly.test/podszywka")
    assert d["url"] == "https://zly.test/podszywka"            # obcy canonical odrzucony
    assert d["author_url"] is None and d["links"] == ["https://ok.test/b"]
    assert d["ground_truth"] == {}                              # etykiety tylko z zaufanego demo
    js = extract_html('<html><head><link rel="canonical" href="javascript:alert(1)"></head><body>x</body></html>',
                      "https://zly.test/x")
    assert js["url"] == "https://zly.test/x"
    sub = extract_html('<html><head><link rel="canonical" href="https://www.youtube.com/watch?v=1"></head><body>x</body></html>',
                       "https://m.youtube.com/watch?v=1")
    assert sub["url"] == "https://www.youtube.com/watch?v=1"   # ta sama witryna – przyjęty


def test_worker_restart_closes_interrupted_jobs():
    from datetime import timedelta

    from iw_backend import tasks
    from iw_backend.db import CrawlJob, session_scope

    with session_scope() as s:
        old = CrawlJob(kind="web", target="x", status="running", started_at=tasks._STARTED_AT - timedelta(hours=1))
        new = CrawlJob(kind="web", target="y", status="running", started_at=tasks._STARTED_AT + timedelta(seconds=1))
        s.add_all([old, new])
        s.flush()
        old_id, new_id = old.id, new.id
    assert tasks._close_interrupted_jobs() >= 1
    with session_scope() as s:
        assert s.get(CrawlJob, old_id).status == "failed" and s.get(CrawlJob, old_id).finished_at
        assert s.get(CrawlJob, new_id).status == "running"      # zadanie bieżącego workera zostaje


def test_evidence_package_zip_hashes_and_escaping(monkeypatch):
    import hashlib
    import io
    import zipfile

    from iw_backend import evidence
    from iw_backend.api import app
    from iw_backend.db import Content, Document, Finding, session_scope, utcnow
    from iw_backend.storage import put_content_addressed

    monkeypatch.setattr(evidence, "_html_to_pdf", lambda html: b"%PDF-1.7 test")   # Chromium nie jest wymagany w CI
    png = b"\x89PNG\r\n\x1a\n" + b"zrzut-testowy"
    with session_scope() as s:
        d = Document(url="https://firma.test/promo", fetched_url="https://firma.test/promo", domain="firma.test",
                     source_type="web", content_hash="h" * 64, title="Promo",
                     raw_key=put_content_addressed(b"<html>oryginal</html>", "raw", "html", "text/html"),
                     screenshots={"desktop": put_content_addressed(png, "screenshots", "png", "image/png")})
        d.content = Content(text="Gwarantowany zysk 20%")
        s.add(d)
        s.flush()
        f = Finding(document_id=d.id, module=2, category="test", score=0.9, rule_score=0.9, excerpt="zysk",
                    event_date=utcnow(), reasons=[{"label": "zysk", "evidence": "<script>alert(1)</script> {N}", "weight": 1}],
                    rules=[{"id": "3", "name": "Ryzyko", "status": "fail", "evidence": "brak", "basis": "art. 44"}])
        s.add(f)
        s.flush()
        fid = f.id
    with TestClient(app) as c:
        assert c.get("/api/findings/999999/evidence").status_code == 404
        r = c.get(f"/api/findings/{fid}/evidence")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    root = z.namelist()[0].split("/")[0]
    names = {n.split("/", 1)[1] for n in z.namelist()}
    assert {"raport.pdf", "raport.html", "dane.json", "tekst.txt", "zrodlo.html", "zrzuty/desktop.png", "SHA256SUMS"} <= names
    sums = z.read(f"{root}/SHA256SUMS").decode().splitlines()
    assert len(sums) == len(names) - 1
    for line in sums:                                    # każdy plik zgadza się ze swoją sumą
        digest, path = line.split("  ", 1)
        assert hashlib.sha256(z.read(f"{root}/{path}")).hexdigest() == digest
    report = z.read(f"{root}/raport.html").decode()
    assert "<script>" not in report and "&lt;script&gt;" in report      # treść ze strony jest tylko tekstem
    assert "zgodny z zapisem z chwili pobrania" in report and "{N}" in report   # treść nie jest modyfikowana
    assert z.read(f"{root}/zrzuty/desktop.png") == png


def test_evidence_pdf_never_raises():
    from iw_backend.evidence import _html_to_pdf

    pdf = _html_to_pdf("<html><body>test</body></html>")
    assert pdf is None or pdf.startswith(b"%PDF")       # bez Chromium: None, teczka ma wtedy sam raport HTML
