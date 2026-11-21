# ScopeOnMedia

Monitoring treści promujących instrumenty i usługi finansowe na polskim rynku.
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

Dashboard: http://localhost:8080 · API: http://localhost:8000/docs (port zmienia `IW_API_PORT` w `.env`).
Bez ustawionych sekretów (albo z wartościami przykładowymi) serwisy celowo nie startują.
Pierwszy start pobiera modele Gemma 4 i Qwen3-Embedding (ok. 5 GB, `docker compose logs -f ollama-init`), a potem `bootstrap` zleca skan danych demo.

### Lokalnie na Windows (bez Dockera)

Wymaga Pythona 3.12 i Node.js 22. Ollama jest opcjonalna: bez niej LLM jest wyłączony, a embeddingi działają w trybie zapasowym.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1          # -Reset: czysta baza
```

Skrypt tworzy `.env` z losowymi sekretami, instaluje zależności
i uruchamia: ai-engine `:8100`, API `:8000`, worker i dashboard `:5173`.

## Wymagania sprzętowe

| Profil | CPU / RAM | Dysk | Uwagi |
|---|---|---|---|
| minimum (`gemma4:e2b`, CPU) | 4 rdzenie / 16 GB | 15 GB | zmierzone (Ryzen 7 4700U, 16 GB): ocena LLM ok. 25–60 s na materiał, w tle |
| zalecany (`gemma4:e4b`) | 8 rdzeni / 32 GB lub GPU 8 GB VRAM | 20 GB | szacunek, niezmierzone; `IW_LLM_MODEL=gemma4:e4b` |
| bez LLM | 2 rdzenie / 4 GB | 3 GB | szacunek, niezmierzone; `IW_LLM_ENGINE=none` |

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
| `IW_INTERNAL_TOKEN` | – | sekret komunikacji worker/ai-engine → API; wymagany, min. 24 znaki – bez niego serwisy nie startują |
| `IW_CORS_ORIGINS` | `http://localhost:5173` (Docker: `:8080`) | adresy, pod którymi zespół otwiera dashboard – inaczej nie działają alerty WebSocket |
| `IW_TRUSTED_LOCAL_HOSTS` / `IW_MAX_PAGE_BYTES` | API demo / 5 MB | lokalne hosty dozwolone mimo ochrony SSRF; maks. rozmiar pobieranej strony |
| `IW_LLM_MODEL` / `IW_EMBED_MODEL` | `gemma4:e2b` / `qwen3-embedding:0.6b` | modele w Ollamie (oba Apache 2.0) |
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
backend\.venv\Scripts\python -m pip install -r requirements-dev.txt      # pytest, pip-audit, uv (analogicznie ai-engine)
backend\.venv\Scripts\python -m pytest backend\tests
ai-engine\.venv\Scripts\python -m pytest ai-engine\tests
backend\.venv\Scripts\python -m iw_backend.cli evaluate        # precyzja / pełność na zbiorze walidacyjnym
powershell -ExecutionPolicy Bypass -File scripts\security-scan.ps1   # pip-audit (lockfile'y) + npm audit → security/
```

Zależności Pythona instaluje się z `requirements.lock` (wszystkie paczki z hashami, `pip install --require-hashes`).
Po zmianie `requirements.txt` odśwież lockfile w katalogu serwisu:
`uv pip compile requirements.txt --universal --generate-hashes --python-version 3.12 --no-header -o requirements.lock`.
GitHub Actions (`.github/workflows/security.yml`) przy każdym pushu i co tydzień sprawdza zgodność lockfile'ów, audytuje
zależności i uruchamia testy oraz build; Dependabot proponuje aktualizacje nie młodsze niż 14 dni.

Architektura, kontrakty i reguły: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · pokrycie wymagań: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) · proces z asystentem AI: [docs/AI_DEV_PROCESS.md](docs/AI_DEV_PROCESS.md).
