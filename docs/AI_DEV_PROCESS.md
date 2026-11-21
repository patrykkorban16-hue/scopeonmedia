# Proces wytwarzania z asystentem AI

Projekt powstał w parze człowiek + asystent kodujący (Claude Code). Asystent pisał kod, a człowiek definiował cel,
dostarczał materiały źródłowe i zatwierdzał zmiany w środowisku (instalacje narzędzi). Proces był powtarzalny i oparty
na weryfikacji, nie na zaufaniu do wygenerowanego kodu.

## Cykl pracy

1. **Specyfikacja jako źródło prawdy.** Opis wyzwania i załączniki (definicja firmy inwestycyjnej, 18 kryteriów
   informacji o ryzyku, art. 76 i art. 2–3 u.o.i.f.) zostały przełożone 1:1 na kod: katalog `RULES` w Module 2,
   elementy A/B/C definicji w Module 3, kategorie rejestru. Pokrycie śledzi [REQUIREMENTS.md](REQUIREMENTS.md).
2. **Przegląd spójności przed przepisaniem.** Wersja 1 została porównana z materiałami. Znalezione rozbieżności:
   - TFI traktowane jako firma inwestycyjna;
   - 7 wymyślonych reguł zamiast 18 z załącznika;
   - brak rozróżnienia kryptoaktywów;
   - AI wewnątrz backendu;
   - podatne wersje Vite/esbuild;
   - obraz MinIO niedostępny w rejestrze.
3. **Implementacja przyrostowa z kontraktami.** Najpierw schematy API (`schemas.py`), potem serwisy.
   Każdy moduł zwraca wyjaśnialne sygnały z dowodem tekstowym.
4. **Weryfikacja na każdym kroku:**
   - testy jednostkowe (`pytest`, 18 testów);
   - ewaluacja na zbiorze walidacyjnym (`cli evaluate`);
   - test end-to-end w przeglądarce: skan → alerty WebSocket → raporty → kalibracja → widok mobilny → konsola;
   - pomiar czasu inferencji LLM;
   - `docker compose config`.
5. **Korekta na podstawie pomiarów, nie intuicji.** Przykłady z tego projektu:
   - detekcja języka myliła polskie „my” i „to” z angielskimi;
   - fleksja („w Banku Nadwiślańskim”) blokowała dopasowanie nazwy;
   - Gemma 4 zwracała pustą odpowiedź przez tryb „thinking” (rozwiązanie: `think: false`);
   - LLM obniżał trafność Modułu 2, bo nie widzi układu strony, więc w M2 został opinią doradczą.
6. **Łańcuch dostaw:**
   - wersje przypięte i wydane co najmniej 2 tygodnie przed instalacją;
   - `pip-audit` i `npm audit` (0 podatności), lockfile'y Pythona z hashami;
   - automatyczny audyt i testy w GitHub Actions oraz Dependabot (aktualizacje nie młodsze niż 14 dni);
   - sekrety wyłącznie w `.env` generowanym losowo.

## Zasady

- Asystent nie zmienia ustawień systemu i nie instaluje oprogramowania bez zgody człowieka.
- Dane demonstracyjne są fikcyjne: nie przypisujemy naruszeń istniejącym firmom.
- Raportujemy też to, czego nie zweryfikowano (stack Docker, tokeny API platform), zamiast to pomijać.
