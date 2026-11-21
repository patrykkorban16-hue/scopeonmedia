# ScopeOnMedia

Monitoring treści promujących instrumenty i usługi finansowe na polskim rynku (wyzwanie UKNF, HackNation 2026).
Silnik scrapingu (WWW + Facebook/Instagram/TikTok/YouTube) i trzy moduły analityczne:

| Moduł | Co wykrywa | Wynik |
|---|---|---|
| M1 Ekosystem zewnętrzny | reklamy firm inwestycyjnych z rejestru KNF u finfluencerów i podmiotów trzecich | firma × reklamujący × treść × URL, okresowa aktualizacja |
| M2 Zgodność i ryzyko | materiały firm inwestycyjnych vs 18 kryteriów z załącznika (art. 44 rozp. 2017/565) | status każdej reguły + flaga |
| M3 Shadow advisory | doradztwo inwestycyjne bez zezwolenia (art. 76 u.o.i.f.) | dane podmiotu, treść oferty, URL |

Dane demonstracyjne (`backend/iw_backend/demo`) opisują **fikcyjne** podmioty na domenach `*.test`. Prawdziwy Rejestr Firm Inwestycyjnych KNF importuje przycisk w zakładce „Źródła” albo `python -m iw_backend.cli registry-knf`.

## Quick Start

### Docker (cały stos jedną komendą)

```bash
cp .env.example .env        # uzupełnij sekrety: IW_INTERNAL_TOKEN, POSTGRES_PASSWORD, S3_SECRET_KEY
docker compose up -d --build
```

Dashboard: http://localhost:8080 · API: http://localhost:8000/docs.
Pierwszy start pobiera modele Gemma 4 i EmbeddingGemma (ok. 5 GB, `docker compose logs -f ollama-init`), a potem `bootstrap` zleca skan danych demo.

### Lokalnie na Windows (bez Dockera)

Wymaga Pythona 3.12 i Node.js 22. Ollama jest opcjonalna: bez niej LLM jest wyłączony, a embeddingi działają w trybie zapasowym.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1          # -Reset: czysta baza
```

Skrypt tworzy `.env` z losowymi sekretami, instaluje zależności i uruchamia: ai-engine `:8100`, API `:8000`, worker i dashboard `:5173`.

## Wymagania sprzętowe

| Profil | CPU / RAM | Dysk | Uwagi |
|---|---|---|---|
| minimum (`gemma4:e2b`, CPU) | 4 rdzenie / 16 GB | 15 GB | ocena LLM ok. 25–60 s na materiał, w tle |
| zalecany (`gemma4:e4b`) | 8 rdzeni / 32 GB lub GPU 8 GB VRAM | 20 GB | `IW_LLM_MODEL=gemma4:e4b` |
| bez LLM | 2 rdzenie / 4 GB | 3 GB | `IW_LLM_ENGINE=none` |

## Serwisy i konfiguracja

| Serwis | Katalog | Port | Rola |
|---|---|---|---|
| frontend | `frontend/` | 8080 (Docker) / 5173 | React + Recharts + Socket.IO |
| api | `backend/` | 8000 | REST, WebSocket, raporty, kalibracja |
| worker | `backend/` | – | kolejka Huey + harmonogram cron, crawler (httpx + Playwright) |
| ai-engine | `ai-engine/` | 8100 | preprocessing, embeddingi, moduły 1–3, agregator, LLM |
| postgres / redis / seaweedfs / ollama | – | wewn. | metadane i treści / kolejka / Object Storage S3 / inferencja |

Najważniejsze zmienne (`.env`, wzór w `.env.example`):

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `IW_INTERNAL_TOKEN` | – | sekret komunikacji worker/ai-engine → API (wymagany) |
| `IW_LLM_MODEL` / `IW_EMBED_MODEL` | `gemma4:e2b` / `embeddinggemma` | modele w Ollamie |
| `IW_LLM_ENGINE` | `ollama` | `ollama`, `openai` (vLLM, llama.cpp server) lub `none` |
| `IW_LLM_REVIEW` | `uncertain` | automatyczna ocena LLM: `all`, `uncertain` (score 0,2–0,85) lub `off` |
| `IW_RENDER_MODE` | `auto` | Playwright: `auto`, `always` lub `never` |
| `IW_PROXIES` | – | lista proxy po przecinku (rotacja) |
| `IW_CRON_WEB`, `IW_CRON_SOCIAL`, `IW_CRON_RECHECK`, `IW_CRON_REGISTRY` | zob. `config.py` | harmonogram w składni cron |
| `IW_META_AD_LIBRARY_TOKEN`, `IW_TIKTOK_RESEARCH_TOKEN`, `IW_INSTAGRAM_GRAPH_TOKEN` | – | bezpłatne oficjalne API; puste = mock demo |
| `IW_REGISTRY_SOURCES` | `demo` | `demo,knf` = także import rejestru KNF |

Źródła do monitorowania: `backend/seeds.json` (seedy crawlera, lista URL, zapytania social/wyszukiwarki).

## Testy i bezpieczeństwo

```powershell
backend\.venv\Scripts\python -m pip install -r requirements-dev.txt      # pytest, pip-audit (analogicznie ai-engine)
backend\.venv\Scripts\python -m pytest backend\tests
ai-engine\.venv\Scripts\python -m pytest ai-engine\tests
backend\.venv\Scripts\python -m iw_backend.cli evaluate        # precyzja / pełność na zbiorze walidacyjnym
powershell -ExecutionPolicy Bypass -File scripts\security-scan.ps1   # pip-audit + npm audit → security/
```

Architektura, kontrakty i reguły: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · pokrycie wymagań: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) · proces z asystentem AI: [docs/AI_DEV_PROCESS.md](docs/AI_DEV_PROCESS.md).
