"""API silnika AI.

    uvicorn iw_ai.main:app --port 8100
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from . import __version__, config
from .aggregator import analyze
from .embeddings import get_embedder
from .llm import get_llm
from .modules.m2_compliance import RULES
from .registry import registry
from .schemas import (AnalyzeRequest, AnalyzeResponse, LLMReviewRequest, LLMReviewResponse, PreprocessRequest,
                      PreprocessResponse)
from .preprocess import preprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
app =FastAPI(title="ScopeOnMedia AI engine", version=__version__)


@app.get("/health")
def health():
    llm = get_llm()
    return {"ok": True, "version": __version__,
            "llm": {"engine": config.LLM_ENGINE, "model": config.LLM_MODEL, "available": llm.available()},
            "embeddings": get_embedder().model_name, "registry": {"version": registry.version,
                                                                  "entities": len(registry.entities)}}


@app.post("/v1/preprocess", response_model=PreprocessResponse)
def v1_preprocess(req: PreprocessRequest):
    return preprocess(req)


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def v1_analyze(req: AnalyzeRequest):
    return analyze(req)


@app.post("/v1/llm-review", response_model=LLMReviewResponse)
def v1_llm_review(req: LLMReviewRequest):
    return get_llm().review(req)


@app.get("/v1/rules")
def v1_rules():
    """Katalog reguł Modułu 2 (lista wymogów z załącznika) – używany przez dashboard."""
    return [{"id": k, "name": v[0], "basis": v[1]} for k, v in RULES.items()]
