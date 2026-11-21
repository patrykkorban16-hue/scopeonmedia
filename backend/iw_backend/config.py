"""Konfiguracja backendu. Wartości domyślne = tryb lokalny (SQLite, kolejka SQLite, pliki lokalne).
Sekrety wyłącznie z pliku .env (wzór: .env.example w katalogu głównym repozytorium)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.getenv("IW_ENV_FILE", Path(__file__).resolve().parents[2] / ".env"))

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("IW_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


# --- bazy -----------------------------------------------------------------------------
DATABASE_URL = os.getenv("IW_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'investwatch.db').as_posix()}")
STORAGE_BACKEND = os.getenv("IW_STORAGE_BACKEND", "local")          # local | s3 (SeaweedFS / dowolne S3)
STORAGE_DIR = Path(os.getenv("IW_STORAGE_DIR", DATA_DIR / "objects"))
S3_ENDPOINT = os.getenv("IW_S3_ENDPOINT", "localhost:8333")
S3_BUCKET = os.getenv("IW_S3_BUCKET", "scopeonmedia")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_SECURE = _b("IW_S3_SECURE", False)

# --- kolejka + harmonogram (Huey) ------------------------------------------------------
QUEUE_BACKEND = os.getenv("IW_QUEUE_BACKEND", "sqlite")             # sqlite | redis
QUEUE_SQLITE = os.getenv("IW_QUEUE_SQLITE", str(DATA_DIR / "queue.db"))
REDIS_URL = os.getenv("IW_REDIS_URL", "redis://localhost:6379/0")
CRON_WEB = os.getenv("IW_CRON_WEB", "0 */6 * * *")
CRON_SOCIAL = os.getenv("IW_CRON_SOCIAL", "30 */2 * * *")
CRON_RECHECK = os.getenv("IW_CRON_RECHECK", "15 3 * * *")          # okresowa aktualizacja znanych reklam (M1)
CRON_REGISTRY = os.getenv("IW_CRON_REGISTRY", "0 4 * * 1")          # import rejestru KNF (co tydzień)

# --- serwisy --------------------------------------------------------------------------
API_PUBLIC_URL = os.getenv("IW_API_URL", "http://127.0.0.1:8000")   # adres API widziany przez worker
AI_ENGINE_URL = os.getenv("IW_AI_ENGINE_URL", "http://127.0.0.1:8100")
INTERNAL_TOKEN = os.getenv("IW_INTERNAL_TOKEN", "")
CORS_ORIGINS = _list("IW_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

# --- scraping -------------------------------------------------------------------------
PROXIES = _list("IW_PROXIES")
REQUEST_TIMEOUT = float(os.getenv("IW_REQUEST_TIMEOUT", "20"))
CRAWL_MAX_PAGES = int(os.getenv("IW_CRAWL_MAX_PAGES", "200"))
CRAWL_MAX_DEPTH = int(os.getenv("IW_CRAWL_MAX_DEPTH", "2"))
CRAWL_DELAY_S = float(os.getenv("IW_CRAWL_DELAY_S", "0.5"))
RESPECT_ROBOTS = _b("IW_RESPECT_ROBOTS", True)
RENDER_MODE = os.getenv("IW_RENDER_MODE", "auto")                   # auto | always | never (Playwright)
SCREENSHOTS = _b("IW_SCREENSHOTS", True)
SEEDS_FILE = Path(os.getenv("IW_SEEDS_FILE", BASE_DIR / "seeds.json"))
REGISTRY_SOURCES = _list("IW_REGISTRY_SOURCES", "demo")             # demo, knf

# tokeny oficjalnych (bezpłatnych) API platform – puste = kolektor czyta mock /demo/api/<platforma>
META_AD_LIBRARY_TOKEN = os.getenv("IW_META_AD_LIBRARY_TOKEN", "")
TIKTOK_RESEARCH_TOKEN = os.getenv("IW_TIKTOK_RESEARCH_TOKEN", "")
INSTAGRAM_GRAPH_TOKEN = os.getenv("IW_INSTAGRAM_GRAPH_TOKEN", "")
SOCIAL_MOCK_BASE = os.getenv("IW_SOCIAL_MOCK_BASE", f"{API_PUBLIC_URL}/demo/api")

DEFAULT_THRESHOLDS = {1: 0.5, 2: 0.5, 3: 0.5}

# Druga opinia LLM: all | uncertain (tylko strefa graniczna score) | off; zawsze możliwa na żądanie analityka
LLM_REVIEW_MODE = os.getenv("IW_LLM_REVIEW", "uncertain")
LLM_BAND = (float(os.getenv("IW_LLM_BAND_LOW", "0.2")), float(os.getenv("IW_LLM_BAND_HIGH", "0.85")))
