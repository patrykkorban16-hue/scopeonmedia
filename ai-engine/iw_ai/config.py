"""Konfiguracja silnika AI (zmienne środowiskowe, zob. .env.example w katalogu głównym)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.getenv("IW_ENV_FILE", Path(__file__).resolve().parents[2] / ".env"))


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# Backend – źródło rejestru podmiotów (firmy inwestycyjne KNF + lista ostrzeżeń)
BACKEND_URL = os.getenv("IW_BACKEND_URL", "http://127.0.0.1:8000")
INTERNAL_TOKEN = os.getenv("IW_INTERNAL_TOKEN", "")

# Silnik inferencji LLM: ollama | openai (vLLM, llama.cpp server – API zgodne z OpenAI) | none
LLM_ENGINE = os.getenv("IW_LLM_ENGINE", "ollama")
OLLAMA_URL = os.getenv("IW_OLLAMA_URL", "http://127.0.0.1:11434")
OPENAI_COMPAT_URL = os.getenv("IW_OPENAI_COMPAT_URL", "http://127.0.0.1:8080/v1")
LLM_MODEL = os.getenv("IW_LLM_MODEL", "gemma4:e2b")
LLM_TIMEOUT = _f("IW_LLM_TIMEOUT", 180)
LLM_WEIGHT = _f("IW_LLM_WEIGHT", 0.35)          # udział oceny LLM w końcowym score (gdy dostępna)

# Embeddingi: ollama (model wielojęzyczny) z fallbackiem na haszowane n-gramy znakowe
EMBED_ENGINE = os.getenv("IW_EMBED_ENGINE", "ollama")   # ollama | hashing
EMBED_MODEL = os.getenv("IW_EMBED_MODEL", "embeddinggemma")
EMBED_DIM_HASHING = 512
