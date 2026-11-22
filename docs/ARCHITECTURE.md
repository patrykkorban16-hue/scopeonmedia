# Architektura ScopeOnMedia

## Przepływ danych

```
seeds.json / API platform ──► Harmonogram (Huey periodic_task, cron) ──► Kolejka (Huey: Redis | SQLite)
                                                                              │ priorytety: zbieranie 10 > recheck 5 > LLM 1
 worker ◄─────────────────────────────────────────────────────────────────────┘
   │  crawler BFS (httpx, robots.txt, rotacja UA + proxy, retry) ─► Playwright: DOM + style w 3 szerokościach + zrzuty ekranu
   │  kolektory: Meta Ad Library, TikTok Research, Instagram Graph (bez tokenów: mock) · strony postów (og:*, JSON-LD)
   ▼
 Object Storage (S3: SeaweedFS | pliki) ◄── surowy HTML/JSON i PNG (klucz = sha256)
   │
   ├─► ai-engine POST /v1/preprocess  → tekst, bloki z cechami wizualnymi, tokeny, SimHash, język, embedding
   │      deduplikacja w backendzie: ten sam serwis = duplikat; inny nadawca = „ten sam przekaz” (kampania)
   ├─► SQL: documents (metadane) · contents (treść, tokeny, embedding, bloki)
   ├─► ai-engine POST /v1/analyze     → moduły 1–3 → agregator → UnifiedFinding[]
   ├─► SQL: findings · alert WebSocket przy pierwszym wejściu w „wysokie ryzyko”
   └─► (asynchronicznie) ai-engine POST /v1/llm-review → Gemma 4 (Ollama) → aktualizacja wyniku + zdarzenie
 API (FastAPI + Socket.IO) ──► dashboard (React, Recharts)
```

Serwisy są niezależne i komunikują się wyłącznie przez HTTP: `backend` (API + worker, ten sam obraz), `ai-engine`
(bezstanowy, rejestr podmiotów pobiera z `GET /internal/registry` i odświeża przy zmianie wersji) oraz `frontend`.
Silnik AI można skalować horyzontalnie, a workery dokładać (Huey na Redis).

## Scoring

Każdy moduł liczy `rule_score = σ(b + Σ wᵢ·xᵢ)` na wyjaśnialnych cechach (reguły z dowodem tekstowym oraz podobieństwo
embeddingu do prototypów). W modułach 1 i 3 ocena LLM jest dokładana asynchronicznie: `score = 0,65·rule_score + 0,35·p_LLM`.
W module 2 opinia LLM jest tylko doradcza, bo model tekstowy nie widzi prezentacji wizualnej (reguły 4–8).

Poziom ryzyka zależy od progu modułu (Panel kalibracji): `score < próg` → niskie (nieflagowane), górna połowa przedziału
nad progiem → wysokie, reszta → średnie. Etykiety kalibracji pochodzą z dwóch źródeł: zbioru walidacyjnego (`iw-ground-truth`)
i decyzji analityków („Potwierdzony” / „Fałszywy alarm”), przy czym decyzja analityka nadpisuje etykietę.

## Moduł 1 – ekosystem zewnętrzny

Materiał wspomina firmę z rejestru (nazwa z tolerancją polskiej fleksji, alias, domena w linku, handle), ale nie jest
opublikowany jej kanałem i jest po polsku. Sygnały za: link afiliacyjny (`ref`, `aff`, `utm_*`, `partner`), kod polecający,
oznaczenie współpracy, wezwanie do otwarcia rachunku, bonus, rekomendacja osobista. Sygnały przeciw: język prasowy,
krytyka, pytania forumowe, deklarowana niezależność rankingu. Reklama bez oznaczenia jest raportowana osobno.
Okresową aktualizację zapewnia `recheck`, który ponownie odwiedza znane reklamy i zapisuje `last_seen` / „usunięta”.

## Moduł 2 – 18 kryteriów (załącznik „kryteria oceny informacji o ryzyku”)

| Reguła | Implementacja |
|---|---|
| 1 identyfikacja firmy | pełna nazwa rejestrowa w treści |
| 2 oznaczenie reklamy | „reklama”, „materiał marketingowy”, #ad… |
| 3 ryzyko przy zyskach | informacja o ryzyku w sąsiedztwie (±2 bloki) każdego twierdzenia o zysku; „bez ryzyka”, „gwarantowany zysk”; CFD bez ostrzeżenia z % rachunków |
| 4 rozmiar czcionki | czcionka ostrzeżenia vs przeważająca (ważona długością tekstu), próg ×0,9 |
| 5 ekspozycja i kontrast | kontrast WCAG (< 4,5:1, < 3:1), przesłonięcie (`elementFromPoint`) |
| 6 ukrywanie | ryzyko wyłącznie w przypisie, sekcji Legal, stopce albo na dole drobnym drukiem |
| 7 dostępność bez kliknięcia | `<details>`, `display:none`, modal, ryzyko tylko pod linkiem |
| 8 responsywność | ostrzeżenie ukryte, ucięte lub < 10 px na tablecie/telefonie; brak meta viewport |
| 9 zrozumiałość | indeks FOG-PL i żargon (instrumenty pochodne, depozyt zabezpieczający…) |
| 10 spójność językowa | język ostrzeżenia ≠ język przeważający materiału |
| 11 porównania | porównanie bez źródła lub założeń |
| 12a / 12b wyniki historyczne | 5 lat, pełne okresy 12-mies., okres referencyjny, źródło / opłaty, waluta obca |
| 13 dominacja wyników | wynik historyczny jako najbardziej eksponowany blok |
| 14 ostrzeżenie przy wynikach | „wyniki historyczne nie są wiarygodnym wskaźnikiem…” |
| 15 prognozy | wykrycie prognozy oraz obecność ostrzeżenia |
| 16 informacja podatkowa | zależność od indywidualnej sytuacji i możliwość zmian |
| 17 aprobata organu | „zatwierdzone / rekomendowane przez KNF” |
| 18 nadzór jako bezpieczeństwo | KNF i „bezpieczne / gwarantowane” w jednym zdaniu |

Cechy wizualne pochodzą z renderowania Playwright (style obliczone, 1366 / 820 / 390 px). Gdy renderowanie jest
niedostępne, działa statyczna kaskada CSS (`<style>`, `@media max-width`, atrybuty `style`).

## Moduł 3 – shadow advisory (art. 76 u.o.i.f.)

Element A to personalizacja (potrzeby lub sytuacja klienta), B to rekomendacja nabycia, zbycia lub trzymania, C to
instrument z katalogu art. 2–3 (akcje, obligacje, jednostki funduszy, ETF, pochodne, CFD). Gdy A, B i C występują
jednocześnie, score dostaje premię. Same kryptoaktywa (poza art. 2) obniżają wynik. Dodatkowe sygnały: odpłatność,
branding (wealth management, family office), Lista ostrzeżeń KNF. Sygnały przeciw: zastrzeżenia, edukacja, doradztwo
podatkowe, model agenta firmy inwestycyjnej. Z treści wyciągane są dane podmiotu: nazwa, NIP, KRS, REGON, e-mail,
telefon, adres.

## Kontrakty API (skrót)

- `POST /v1/preprocess {url, source_type, html?, text?, render?}` → `{text, blocks[], tokens, simhash, language, embedding, style_source}`
- `POST /v1/analyze {document, pre, registry_version}` → `{findings: UnifiedFinding[], max_score}`
- `UnifiedFinding = {module, category, score, rule_score, firm, advertiser, entity, excerpt, reasons[], rules[], details}`
- `GET /api/findings/{id}/evidence` → teczka dowodowa (ZIP): raport PDF/HTML, zrzuty ekranu, surowe źródło, `dane.json`,
  `SHA256SUMS`; zrzuty i źródło są w storage pod kluczem = SHA-256 z chwili pobrania, więc raport potwierdza ich niezmienność
- Zdarzenia Socket.IO: `alert`, `finding_updated`, `thresholds`, `job`, `registry`

## Bezpieczeństwo

Treść zbierana z internetu jest traktowana jako wrogie dane wejściowe (`backend/iw_backend/security.py`):

| Zagrożenie | Zabezpieczenie |
|---|---|
| Dostęp do dashboardu i API | porty dashboardu i API wystawione tylko na `127.0.0.1` (bez logowania w MVP); `/internal/*` (rejestr, zdarzenia) – token serwisowy |
| XSS przez linki ze stron | tylko adresy `http(s)` w bazie (`safe_url`) i w dashboardzie (`safeHref`); CSP w nginx |
| Podszywanie się pod stronę firmy | adres kanoniczny przyjmowany tylko z tej samej witryny; etykiety walidacyjne tylko z lokalnego demo |
| SSRF (crawler jako proxy do sieci wewnętrznej) | blokada adresów prywatnych, loopback i link-local – przed każdym zapytaniem, każdym przekierowaniem i każdym zasobem ładowanym przez Playwright; limit rozmiaru odpowiedzi |
| Formuły w eksporcie CSV | komórki zaczynające się od `= + - @` poprzedzone apostrofem |
| Prompt injection (strona steruje LLM) | treść oznaczona jako dane, wykrywanie typowych poleceń (ocena pominięta, sygnał dla analityka), LLM może obniżyć wynik reguł najwyżej o 0,15 |
| Sekrety | tylko w `.env` (poza repozytorium), losowane kryptograficznie; serwisy nie startują bez nich lub z wartościami przykładowymi |
| Łańcuch dostaw | lockfile'y z hashami, obrazy Docker przypięte digestem (`tag@sha256`), `npm ci --ignore-scripts`, pip-audit, npm audit, ruff (bandit), CI co tydzień, Dependabot (pip, npm, Docker, Actions) z 14-dniowym opóźnieniem |

## Ograniczenia MVP

- Zbiór walidacyjny jest mały (44 materiały) i przygotowany razem z regułami. Wyniki na nim nie są miarą skuteczności
  na realnych danych; przed pilotażem potrzebna jest oznaczona próbka rzeczywistych materiałów.
- Tokeny oficjalnych API platform nie były testowane. Kolektory zgodne z dokumentacją API działają w demo na mocku.
- Lista ostrzeżeń publicznych KNF jest w demo wpisana ręcznie; automatyczny import obejmuje rejestr firm inwestycyjnych.
- Wyszukiwanie near-duplikatów jest liniowe (do 20 tys. ostatnich dokumentów); na większą skalę potrzebny jest indeks LSH.
- Brak logowania: dashboard i API są dostępne dla każdego, kto ma dostęp do komputera (porty tylko na `127.0.0.1`),
  a historia statusów nie zapisuje, który analityk podjął decyzję. Przy wdrożeniu – konta imienne (np. SSO/LDAP Urzędu)
  i reverse proxy z TLS.
- Ochrona SSRF sprawdza adres DNS przed zapytaniem; atak DNS rebinding (zmiana adresu między sprawdzeniem a połączeniem)
  wymagałby dodatkowo przypinania IP lub serwera proxy z listą dozwolonych adresów.
- Brak polityki retencji zebranych danych osobowych (NIP, e-maile, telefony z ofert) – do ustalenia z IOD przed pilotażem.
