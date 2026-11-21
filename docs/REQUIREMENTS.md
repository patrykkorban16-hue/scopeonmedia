# Pokrycie wymagań (opis wyzwania UKNF + załączniki)

Status: **✔ zweryfikowane** = uruchomione i sprawdzone lokalnie (testy, przeglądarka, pomiar) · **◐ zaimplementowane, niezweryfikowane** = kod gotowy, brak środowiska do uruchomienia.

| Wymaganie | Implementacja | Status |
|---|---|---|
| Kolejka zadań open source | Huey (`backend/iw_backend/tasks.py`), priorytety, retry | ✔ (SQLite) · ◐ (Redis w Dockerze) |
| Playwright / httpx | `scraper/http.py`, `scraper/render.py` | ✔ |
| Kolektory social media, rotacja UA i proxy | `scraper/collectors.py`, `scraper/http.py` (`IW_PROXIES`) | ✔ mock + parser stron (og:*, JSON-LD) · ◐ prawdziwe tokeny API |
| HTML → JSON | `scraper/extract.py` | ✔ |
| Baza metadanych SQL, baza treści + Object Storage | `db.py` (documents / contents / findings), `storage.py` | ✔ SQLite + pliki · ◐ PostgreSQL + SeaweedFS |
| CronJob | `@huey.periodic_task(crontab)` – web, social, recheck, rejestr KNF, heartbeat | ✔ |
| Usuwanie tagów, normalizacja, deduplikacja | `ai-engine/iw_ai/preprocess.py`, `text.py` (sha256 + SimHash) | ✔ |
| Tokeny i embeddingi | `embeddings.py` – EmbeddingGemma w Ollamie, zapasowo haszowane n-gramy | ✔ |
| Silnik inferencji, model open source | Ollama + `gemma4:e2b`; vLLM / llama.cpp przez API OpenAI | ✔ Ollama · ◐ vLLM |
| Klasyfikacja przez funkcję scoringową | `scoring.py`, moduły `m1/m2/m3` | ✔ |
| Agregator 1+2+3 | `aggregator.py` → `UnifiedFinding` | ✔ |
| Filtry: data, źródło, ryzyko, moduł | `/api/findings`, `FilterBar.jsx` | ✔ |
| Wykresy trendów | `TrendChart.jsx` (Recharts; data publikacji / wykrycia) | ✔ |
| Zmiana statusu rekordu | `PATCH /api/findings/{id}` + historia | ✔ |
| WebSocket – alert wysokiego ryzyka | Socket.IO `alert`, `AlertToasts.jsx` | ✔ (alerty na żywo w trakcie skanu) |
| Panel kalibracji: próg → FP/FN | `/api/calibration/{m}`, `CalibrationPanel.jsx` | ✔ |
| Architektura oparta o propsy | komponenty funkcyjne bez stanu globalnego | ✔ |
| M1: firma, reklamujący, treść, URL, okresowa aktualizacja | `m1_ecosystem.py`, `/api/reports/m1`, `recheck` | ✔ |
| M2: 18 kryteriów z załącznika | `m2_compliance.py`, macierz `/api/reports/m2` | ✔ (testy jednostkowe dla reguł 1, 3, 10, 14, 17, 18 i responsywności) |
| M3: dane podmiotu, treść, URL; definicja art. 76 | `m3_shadow.py`, `entity_extract.py`, `/api/reports/m3` | ✔ |
| Definicja firmy inwestycyjnej (zał. 1/2) | kategorie rejestru + importer stron KNF (`registry/knf.py`) | ✔ import na żywo 21.11.2026: 760 podmiotów (28 DM, 10 banków, 10 oddziałów, 712 transgranicznych) |
| Separacja frontend / backend / AI | 3 katalogi, 3 obrazy, komunikacja HTTP | ✔ |
| Docker Compose – start jedną komendą | `docker-compose.yml` (healthchecki, pobieranie modeli, bootstrap) | ◐ `docker compose config` poprawny; brak WSL2 na maszynie deweloperskiej |
| Tylko darmowe modele i otwarte bazy | Gemma 4, EmbeddingGemma, PostgreSQL, Redis, SeaweedFS | ✔ |
| Skan zależności, sekrety w .env | `scripts/security-scan.ps1` (pip-audit, npm audit), `.env.example` | ✔ 0 podatności (21.11.2026) |
| README: Quick Start, sprzęt, konfiguracja | `README.md` | ✔ |
| Console.log | brak `console.*` w kodzie; konsola bez błędów po załadowaniu | ✔ |

## Wyniki na zbiorze walidacyjnym (próg 0,5)

| Moduł | TP | FP | FN | TN | Precyzja | Pełność |
|---|---|---|---|---|---|---|
| M1 | 9 | 0 | 0 | 5 | 1,00 | 1,00 |
| M2 | 11 | 0 | 2 | 5 | 1,00 | 0,85 |
| M3 | 7 | 0 | 0 | 5 | 1,00 | 1,00 |

Dwa przeoczenia w M2 to celowe przypadki graniczne: jedno uchybienie reguły 16 i jedno reguły 11 (score 0,38 i 0,46).
Obniżenie progu M2 do 0,35 wykrywa oba bez dodatkowych fałszywych alarmów. Zbiór jest mały i przygotowany razem
z regułami, więc nie odzwierciedla skuteczności na danych rzeczywistych.
