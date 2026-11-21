"""Zdarzenia czasu rzeczywistego: worker (osobny proces) → API → Socket.IO → dashboard."""
from __future__ import annotations

import logging

import httpx

from . import config

log = logging.getLogger(__name__)


def publish(events: list[dict]) -> None:
    if not events:
        return
    try:
        httpx.post(f"{config.API_PUBLIC_URL}/internal/events", json={"events": events}, timeout=5,
                   headers={"X-Internal-Token": config.INTERNAL_TOKEN})
    except Exception as exc:
        log.info("API nieosiągalne dla zdarzeń (%s)", exc)
