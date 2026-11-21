"""Logowanie do dashboardu: hasło zespołu z .env, sesja w podpisanym ciasteczku (HttpOnly, SameSite=Strict).

Sesja jest bezstanowa: `<wygaśnięcie>.<nonce>.<HMAC>`; klucz HMAC pochodzi z sekretu serwisu i hasła,
więc zmiana hasła unieważnia wszystkie sesje. Nieudane logowania są ograniczane (5 prób / 5 min / adres).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from http.cookies import SimpleCookie

from . import config

COOKIE = "iw_session"
SESSION_TTL = 12 * 3600
MAX_FAILURES, WINDOW_S = 5, 300
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def _key() -> bytes:
    return hashlib.sha256(b"iw-session|" + config.INTERNAL_TOKEN.encode() + b"|" + config.DASHBOARD_PASSWORD.encode()).digest()


def _sign(msg: str) -> str:
    return hmac.new(_key(), msg.encode(), hashlib.sha256).hexdigest()


def make_session() -> str:
    msg = f"{int(time.time()) + SESSION_TTL}.{secrets.token_hex(8)}"
    return f"{msg}.{_sign(msg)}"


def valid_session(value: str | None) -> bool:
    if not value or value.count(".") != 2:
        return False
    exp, nonce, sig = value.split(".")
    if not exp.isdigit() or int(exp) < time.time():
        return False
    return hmac.compare_digest(sig, _sign(f"{exp}.{nonce}"))


def check_password(password: str) -> bool:
    return bool(config.DASHBOARD_PASSWORD) and hmac.compare_digest(password.encode(), config.DASHBOARD_PASSWORD.encode())


def rate_limited(client: str) -> bool:
    now = time.time()
    with _lock:
        recent = [t for t in _failures.get(client, []) if now - t < WINDOW_S]
        _failures[client] = recent
        return len(recent) >= MAX_FAILURES


def record_failure(client: str) -> None:
    with _lock:
        _failures.setdefault(client, []).append(time.time())


def clear_failures(client: str) -> None:
    with _lock:
        _failures.pop(client, None)


def cookie_from_environ(environ: dict) -> str | None:
    """Sesja z nagłówka Cookie połączenia WebSocket (Socket.IO)."""
    raw = environ.get("HTTP_COOKIE", "")
    if not raw:
        return None
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        return None
    return jar[COOKIE].value if COOKIE in jar else None
