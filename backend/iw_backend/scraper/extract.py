"""Ekstrakcja danych z HTML do ujednoliconego formatu JSON (metadane materiału).

Pełny preprocessing treści (bloki, style, tokeny, embedding) wykonuje silnik AI – tu wyciągamy to, czego
potrzebuje crawler i baza metadanych: kanoniczny URL, autor, data, linki, platforma, metryki.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..security import is_trusted_local, safe_url, same_site

SOCIAL_HOSTS = {"facebook.com": "facebook", "fb.com": "facebook", "instagram.com": "instagram", "tiktok.com": "tiktok",
                "youtube.com": "youtube", "youtu.be": "youtube", "x.com": "x", "twitter.com": "x", "linkedin.com": "linkedin"}


def _norm(s: str | None) -> str | None:
    return re.sub(r"\s+", " ", s).strip() if s else None


def _meta(soup, *names: str) -> str | None:
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return _norm(tag["content"])
    return None


def parse_date(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None) if value > 10_000 else None
    v = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(v[:10], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def platform_of(url: str) -> str:
    d = domain_of(url)
    for host, name in SOCIAL_HOSTS.items():
        if d == host or d.endswith("." + host):
            return name
    return "web"


def _jsonld(soup) -> list[dict]:
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        out += data if isinstance(data, list) else [data]
    return [d for d in out if isinstance(d, dict)]


def extract_html(html: str, fetched_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    trusted = is_trusted_local(fetched_url)
    link = soup.find("link", rel=lambda v: v and "canonical" in v)
    canonical = safe_url(urljoin(fetched_url, link["href"])) if link and link.get("href") else None
    # obca witryna nie może „przejąć” adresu innej strony (np. firmy z rejestru); wyjątek: lokalne dane demo
    url = canonical if canonical and (trusted or same_site(canonical, fetched_url)) else fetched_url
    ld = _jsonld(soup)
    ld_author = next((d.get("author") for d in ld if d.get("author")), None)
    if isinstance(ld_author, list):
        ld_author = ld_author[0] if ld_author else None
    author = _meta(soup, "author", "article:author", "twitter:creator") or (
        ld_author.get("name") if isinstance(ld_author, dict) else ld_author)
    author_url = safe_url(ld_author.get("url")) if isinstance(ld_author, dict) else None
    if not author_url:
        a = soup.find("a", attrs={"rel": "author"})
        author_url = safe_url(urljoin(url, a["href"])) if a and a.get("href") else None
    published = (_meta(soup, "article:published_time", "date", "pubdate")
                 or next((d.get("datePublished") or d.get("uploadDate") for d in ld if d.get("datePublished") or d.get("uploadDate")), None))
    if not published:
        t = soup.find("time", attrs={"datetime": True})
        published = t["datetime"] if t else None
    links = []
    for a in soup.find_all("a", href=True):
        h = safe_url(urljoin(fetched_url, a["href"].strip()))
        if h:
            links.append(h)
    metrics = {}
    for d in ld:
        for st in (d.get("interactionStatistic") or []):
            if isinstance(st, dict) and st.get("userInteractionCount") is not None:
                kind = str(st.get("interactionType", "")).split("/")[-1] or "interactions"
                metrics[kind] = st["userInteractionCount"]
    robots = (_meta(soup, "robots") or "").lower()
    html_tag = soup.find("html")
    title = _norm(soup.title.get_text()) if soup.title else _meta(soup, "og:title")
    platform = platform_of(url)
    return {
        "url": url, "fetched_url": fetched_url, "domain": domain_of(url), "source_type": platform,
        "title": title, "description": _meta(soup, "description", "og:description"),
        "site_name": _meta(soup, "og:site_name", "application-name"),
        "author": _norm(author), "author_url": author_url, "published_at": parse_date(published),
        "language": ((html_tag.get("lang") if html_tag else None) or "")[:2].lower() or None,
        "links": list(dict.fromkeys(links))[:500], "metrics": metrics,
        "noindex": "noindex" in robots,
        # etykiety walidacyjne wyłącznie z zaufanego, lokalnego zbioru demo – obca strona nie zafałszuje kalibracji
        "ground_truth": _ground_truth(soup) if trusted else {},
    }


def _ground_truth(soup) -> dict:
    gt = soup.find("meta", attrs={"name": "iw-ground-truth"})
    try:
        data = json.loads(gt["content"]) if gt and gt.get("content") else {}
    except (ValueError, TypeError):
        return {}
    return {str(k): bool(v) for k, v in data.items() if str(k) in {"1", "2", "3"}} if isinstance(data, dict) else {}


def extract_social_item(item: dict, trusted: bool = False) -> dict | None:
    """Post / reklama z API platformy → ten sam format metadanych + tekst do preprocessingu.
    `trusted` = dane z lokalnego mocka demo (tylko wtedy przyjmujemy etykiety walidacyjne)."""
    url = safe_url(item.get("url"))
    if not url:
        return None
    text = "\n".join(filter(None, [item.get("title"), item.get("text"), item.get("caption"),
                                   " ".join(item.get("hashtags", []))]))
    gt = item.get("ground_truth") if trusted and isinstance(item.get("ground_truth"), dict) else {}
    return {
        "url": url, "fetched_url": safe_url(item.get("fetched_url")) or url, "domain": domain_of(url),
        "source_type": item.get("platform") or platform_of(url), "title": (item.get("title") or text[:140]) or None,
        "description": None, "site_name": item.get("platform"), "author": item.get("author"),
        "author_url": safe_url(item.get("author_url")), "published_at": parse_date(item.get("published_at")),
        "language": item.get("language"), "links": [u for u in map(safe_url, item.get("links", [])) if u],
        "metrics": item.get("metrics", {}), "ad_meta": item.get("ad_meta"), "noindex": False,
        "ground_truth": {str(k): bool(v) for k, v in gt.items() if str(k) in {"1", "2", "3"}},
        "text": text,
    }
