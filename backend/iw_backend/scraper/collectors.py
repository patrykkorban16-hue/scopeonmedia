"""Kolektory danych.

* crawl_web – crawler BFS (httpx do odkrywania linków + Playwright do renderowania stron z treścią),
* fetch_page – pojedynczy URL (lista monitorowanych adresów, ponowne odwiedziny znanych reklam),
* search_web – wyszukiwarka HTML (opcjonalnie, domyślnie wyłączona),
* social – oficjalne, bezpłatne API platform (Meta Ad Library, TikTok Research API, Instagram Graph API)
  z rotacją UA/proxy; bez tokenów – mock /demo/api/<platforma> w identycznym formacie.
  Publiczne strony postów (og:*, JSON-LD) obsługuje fetch_page → extract_html.
"""
from __future__ import annotations

import json
import logging
import re
from collections import deque
from typing import Iterator
from urllib.parse import parse_qs, unquote, urldefrag, urlparse

import httpx

from .. import config
from . import render as renderer
from .extract import extract_html, extract_social_item
from .http import Fetcher, headers

log = logging.getLogger(__name__)
SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|webp|svg|pdf|zip|mp4|mp3|css|js|ico|woff2?|xml)(\?|$)", re.I)


def fetch_page(url: str, fetcher: Fetcher, *, render: bool | None = None) -> dict | None:
    """Pobiera stronę; zwraca {meta, html, render, screenshots, status} albo None (błąd / robots.txt)."""
    if not fetcher.allowed(url):
        log.info("robots.txt blokuje %s", url)
        return None
    use_render = renderer.available() if render is None else render
    try:
        r = fetcher.get(url)
    except Exception as exc:
        log.warning("błąd pobierania %s: %s", url, exc)
        return None
    if r.status_code >= 400:
        return {"meta": None, "status": r.status_code}
    if "html" not in r.headers.get("content-type", "text/html"):
        return None
    html, rep, shots = r.text, None, {}
    if use_render and config.RENDER_MODE != "never":
        try:
            out = renderer.render(str(r.url), proxy=fetcher.next_proxy())
            html, rep, shots = out["html"], out["render"], out["screenshots"]
        except Exception as exc:
            log.warning("Playwright nie wyrenderował %s (%s) – analiza statyczna", url, exc)
            if config.RENDER_MODE == "always":
                raise
    meta = extract_html(html, str(r.url))
    return {"meta": meta, "html": html, "render": rep, "screenshots": shots, "status": r.status_code}


def crawl_web(seed_url: str, *, max_depth: int | None = None, max_pages: int | None = None,
              allow_domains: list[str] | None = None, fetcher: Fetcher | None = None) -> Iterator[dict]:
    max_depth = config.CRAWL_MAX_DEPTH if max_depth is None else max_depth
    max_pages = config.CRAWL_MAX_PAGES if max_pages is None else max_pages
    fetcher = fetcher or Fetcher()
    hosts = {urlparse(seed_url).netloc, *(allow_domains or [])}
    queue: deque[tuple[str, int]] = deque([(seed_url, 0)])
    seen = {seed_url}
    pages = 0
    while queue and pages < max_pages:
        url, depth = queue.popleft()
        page = fetch_page(url, fetcher)
        if not page or not page.get("meta"):
            continue
        pages += 1
        meta = page["meta"]
        if not meta["noindex"]:                     # strony-huby (noindex) służą tylko do odkrywania linków
            yield page
        if depth >= max_depth:
            continue
        for link in meta["links"]:
            link = urldefrag(link)[0]
            if link in seen or SKIP_EXT.search(link) or not link.startswith("http") or urlparse(link).netloc not in hosts:
                continue
            seen.add(link)
            queue.append((link, depth + 1))


def search_web(query: str, fetcher: Fetcher, limit: int = 10) -> list[str]:
    r = fetcher.get("https://html.duckduckgo.com/html/", params={"q": query, "kl": "pl-pl"})
    urls = []
    for href in re.findall(r'class="result__a"[^>]+href="([^"]+)"', r.text):
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if href.startswith("http") and href not in urls:
            urls.append(href)
    return urls[:limit]


# ---------------------------------------------------------------------------- social media
def _mock(platform: str, query: str, fetcher: Fetcher) -> list[dict]:
    r = fetcher.get(f"{config.SOCIAL_MOCK_BASE}/{platform}", params={"q": query})
    r.raise_for_status()
    return r.json()["data"]


def collect_meta_ads(query: str, fetcher: Fetcher) -> list[dict]:
    """Meta Ad Library API – reklamy emitowane w PL (Facebook + Instagram)."""
    if not config.META_AD_LIBRARY_TOKEN:
        return _mock("facebook", query, fetcher)
    r = fetcher.get("https://graph.facebook.com/v21.0/ads_archive", params={
        "access_token": config.META_AD_LIBRARY_TOKEN, "search_terms": query, "ad_reached_countries": '["PL"]',
        "ad_active_status": "ALL", "ad_type": "ALL", "languages": '["pl"]', "limit": 50,
        "fields": "id,ad_snapshot_url,ad_creative_bodies,ad_creative_link_titles,ad_creative_link_captions,"
                  "page_id,page_name,ad_delivery_start_time,publisher_platforms,eu_total_reach"})
    r.raise_for_status()
    out = []
    for ad in r.json().get("data", []):
        plats = ad.get("publisher_platforms") or ["facebook"]
        out.append({"platform": "instagram" if plats == ["instagram"] else "facebook",
                    "url": f"https://www.facebook.com/ads/library/?id={ad['id']}",
                    "author": ad.get("page_name"), "author_url": f"https://www.facebook.com/{ad.get('page_id')}",
                    "title": " ".join(ad.get("ad_creative_link_titles") or []),
                    "text": "\n".join(ad.get("ad_creative_bodies") or []),
                    "links": ad.get("ad_creative_link_captions") or [], "published_at": ad.get("ad_delivery_start_time"),
                    "metrics": {"eu_total_reach": ad.get("eu_total_reach")}, "ad_meta": {"ad_id": ad["id"], "platforms": plats}})
    return out


def collect_tiktok(query: str, fetcher: Fetcher) -> list[dict]:
    """TikTok Research API (dostęp badawczy, bezpłatny)."""
    if not config.TIKTOK_RESEARCH_TOKEN:
        return _mock("tiktok", query, fetcher)
    r = httpx.post("https://open.tiktokapis.com/v2/research/video/query/?fields=id,video_description,create_time,"
                   "username,hashtag_names,view_count,like_count,region_code", timeout=30,
                   headers={"Authorization": f"Bearer {config.TIKTOK_RESEARCH_TOKEN}", **headers()},
                   proxy=fetcher.next_proxy(),
                   json={"query": {"and": [{"operation": "IN", "field_name": "region_code", "field_values": ["PL"]},
                                           {"operation": "IN", "field_name": "keyword", "field_values": [query]}]},
                         "max_count": 100, "start_date": "20260101", "end_date": "20261231"})
    r.raise_for_status()
    return [{"platform": "tiktok", "url": f"https://www.tiktok.com/@{v['username']}/video/{v['id']}",
             "author": "@" + v["username"], "author_url": f"https://www.tiktok.com/@{v['username']}",
             "text": v.get("video_description", ""), "hashtags": ["#" + h for h in v.get("hashtag_names", [])],
             "published_at": v.get("create_time"), "metrics": {"views": v.get("view_count"), "likes": v.get("like_count")}}
            for v in r.json().get("data", {}).get("videos", [])]


def collect_instagram(query: str, fetcher: Fetcher) -> list[dict]:
    """Instagram Graph API – wyszukiwanie po hashtagu (token konta biznesowego: '<ig_user_id>:<token>')."""
    if not config.INSTAGRAM_GRAPH_TOKEN:
        return _mock("instagram", query, fetcher)
    user_id, token = config.INSTAGRAM_GRAPH_TOKEN.split(":", 1)
    tag = re.sub(r"\W", "", query.lower())
    h = fetcher.get("https://graph.facebook.com/v21.0/ig_hashtag_search",
                    params={"user_id": user_id, "q": tag, "access_token": token}).json()
    hid = (h.get("data") or [{}])[0].get("id")
    if not hid:
        return []
    media = fetcher.get(f"https://graph.facebook.com/v21.0/{hid}/recent_media", params={
        "user_id": user_id, "access_token": token, "fields": "id,caption,permalink,timestamp,like_count"}).json()
    return [{"platform": "instagram", "url": m["permalink"], "text": m.get("caption", ""), "published_at": m.get("timestamp"),
             "metrics": {"likes": m.get("like_count")}} for m in media.get("data", [])]


SOCIAL = {"facebook": collect_meta_ads, "tiktok": collect_tiktok, "instagram": collect_instagram}


def collect_social(platform: str, query: str, fetcher: Fetcher | None = None) -> Iterator[dict]:
    fetcher = fetcher or Fetcher()
    for item in SOCIAL[platform](query, fetcher):
        item.setdefault("platform", platform)
        meta = extract_social_item(item)
        yield {"meta": meta, "text": meta.pop("text"), "raw": json.dumps(item, ensure_ascii=False).encode("utf-8"),
               "status": 200}
