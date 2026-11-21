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
