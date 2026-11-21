"""Zabezpieczenia danych wejściowych z internetu.

* safe_url – tylko http(s): odrzuca javascript:, data:, vbscript: itp. (XSS przez linki w dashboardzie),
* fetch_allowed – ochrona przed SSRF: crawler nie odwiedza adresów prywatnych, lokalnych ani link-local
  (wyjątek: hosty z IW_TRUSTED_LOCAL_HOSTS, np. lokalny mini-internet demonstracyjny),
* same_site – adres kanoniczny strony przyjmujemy tylko z tej samej witryny (inaczej obca strona mogłaby
  nadpisać materiał firmy z rejestru i przypisać jej naruszenia),
* csv_safe – neutralizacja formuł w eksporcie CSV (=, +, -, @ na początku komórki).
"""
from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache
from urllib.parse import urlparse

from . import config

SAFE_SCHEMES = {"http", "https"}
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_url(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip()
    try:
        u = urlparse(v)
    except ValueError:
        return None
    if u.scheme.lower() not in SAFE_SCHEMES or not u.hostname:
        return None
    return v


def _netloc(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def is_trusted_local(url: str) -> bool:
    return _netloc(url) in config.TRUSTED_LOCAL_HOSTS


@lru_cache(maxsize=4096)
def _resolve(host: str) -> tuple[str, ...]:
    try:
        return tuple(sorted({ai[4][0] for ai in socket.getaddrinfo(host, None)}))
    except (socket.gaierror, UnicodeError):
        return ()


def is_public_host(host: str | None) -> bool:
    """Wszystkie adresy IP hosta muszą być publiczne (nie: prywatne, loopback, link-local, zarezerwowane)."""
    if not host:
        return False
    ips = _resolve(host.lower())
    if not ips:
        return False
    for ip in ips:
        try:
            if not ipaddress.ip_address(ip.split("%")[0]).is_global:
                return False
        except ValueError:
            return False
    return True


def fetch_allowed(url: str | None) -> bool:
    if not safe_url(url):
        return False
    if is_trusted_local(url):
        return True
    return is_public_host(urlparse(url).hostname)


def _site(host: str) -> str:
    return host.lower().removeprefix("www.")


def same_site(a: str, b: str) -> bool:
    """Ten sam host albo relacja domena–subdomena (m.youtube.com ~ youtube.com)."""
    ha, hb = _site(urlparse(a).hostname or ""), _site(urlparse(b).hostname or "")
    return bool(ha and hb) and (ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha))


def csv_safe(value):
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return "'" + value
    return value
