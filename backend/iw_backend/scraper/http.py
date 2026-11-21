"""Klient HTTP silnika scrapingu: rotacja User-Agent i proxy (pula z wyłączaniem niedziałających),
retry z wykładniczym backoffem, obsługa robots.txt i limitu tempa per domena."""
from __future__ import annotations

import itertools
import logging
import random
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .. import config

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 16; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
]
ROBOTS_AGENT = "ScopeOnMediaBot"


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def headers() -> dict[str, str]:
    return {"User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.6"}


class ProxyPool:
    """Round-robin; proxy, które zawiodło, jest pomijane przez 5 minut."""

    def __init__(self, proxies: list[str]):
        self.proxies = proxies
        self._cycle = itertools.cycle(proxies) if proxies else None
        self._dead: dict[str, float] = {}
        self._lock = threading.Lock()

    def next(self) -> str | None:
        if not self._cycle:
            return None
        with self._lock:
            for _ in range(len(self.proxies)):
                p = next(self._cycle)
                if time.time() - self._dead.get(p, 0) > 300:
                    return p
        return None

    def mark_bad(self, proxy: str | None) -> None:
        if proxy:
            self._dead[proxy] = time.time()


class Fetcher:
    def __init__(self, proxies: list[str] | None = None, delay_s: float | None = None):
        self.pool = ProxyPool(config.PROXIES if proxies is None else proxies)
        self.delay = config.CRAWL_DELAY_S if delay_s is None else delay_s
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._clients: dict[str | None, httpx.Client] = {}

    def _client(self, proxy: str | None) -> httpx.Client:
        if proxy not in self._clients:
            self._clients[proxy] = httpx.Client(proxy=proxy, timeout=config.REQUEST_TIMEOUT, follow_redirects=True)
        return self._clients[proxy]

    def next_proxy(self) -> str | None:
        return self.pool.next()

    def allowed(self, url: str) -> bool:
        if not config.RESPECT_ROBOTS:
            return True
        u = urlparse(url)
        base = f"{u.scheme}://{u.netloc}"
        if base not in self._robots:
            try:
                r = self._client(None).get(base + "/robots.txt", headers=headers(), timeout=8)
                rp = RobotFileParser()
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
                self._robots[base] = rp
            except Exception:
                self._robots[base] = None
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(ROBOTS_AGENT, url)

    def _throttle(self, host: str) -> None:
        wait = self.delay - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.time()

    def get(self, url: str, *, params: dict | None = None, extra_headers: dict | None = None,
            retries: int = 3) -> httpx.Response:
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(retries):
            proxy = self.pool.next()
            self._throttle(host)
            try:
                r = self._client(proxy).get(url, params=params, headers={**headers(), **(extra_headers or {})})
                if r.status_code in (429, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                return r
            except Exception as exc:
                last = exc
                self.pool.mark_bad(proxy)
                time.sleep(min(8.0, 2 ** attempt + random.random()))
        raise last  # type: ignore[misc]

    def close(self) -> None:
        for c in self._clients.values():
            c.close()
