"""Klient HTTP silnika AI (osobny serwis, kontrakt /v1)."""
from __future__ import annotations

import httpx

from . import config

_client = httpx.Client(base_url=config.AI_ENGINE_URL, timeout=httpx.Timeout(120, connect=5))


def _post(path: str, payload: dict, timeout: float | None = None) -> dict:
    r = _client.post(path, json=payload, timeout=timeout or 120)
    r.raise_for_status()
    return r.json()


def preprocess(url: str, source_type: str, html: str | None = None, text: str | None = None,
               render: dict | None = None) -> dict:
    return _post("/v1/preprocess", {"url": url, "source_type": source_type, "html": html, "text": text, "render": render})


def analyze(document: dict, pre: dict, registry_version: str | None) -> dict:
    return _post("/v1/analyze", {"document": document, "pre": pre, "registry_version": registry_version})


def llm_review(module: int, text: str, context: str, rule_score: float) -> dict:
    return _post("/v1/llm-review", {"module": module, "text": text, "context": context, "rule_score": rule_score},
                 timeout=600)


def health() -> dict:
    try:
        return _client.get("/health", timeout=8).json()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def rules() -> list[dict]:
    return _client.get("/v1/rules", timeout=5).json()
