"""Silnik inferencji LLM – lokalny model open source (domyślnie Gemma w Ollamie; alternatywnie vLLM lub
llama.cpp server przez API zgodne z OpenAI). Służy jako druga opinia: zwraca prawdopodobieństwo naruszenia
i uzasadnienie po polsku, które backend dokłada do wyniku asynchronicznie (kolejka o niskim priorytecie)."""
from __future__ import annotations

import json
import logging
import re
import time

import httpx

from . import config
from .schemas import LLMReviewRequest, LLMReviewResponse

log = logging.getLogger(__name__)

SYSTEM = ("Jesteś analitykiem Urzędu Komisji Nadzoru Finansowego. Oceniasz polskojęzyczne materiały dotyczące "
          "instrumentów i usług finansowych. Odpowiadasz wyłącznie poprawnym obiektem JSON.")

TASKS = {
    1: ("Oceń, czy materiał jest REKLAMĄ (promocją) usług lub instrumentów firmy inwestycyjnej, zamieszczoną przez "
        "podmiot trzeci lub osobę prywatną (np. finfluencera): linki afiliacyjne, kody polecające, zachęta do otwarcia "
        "rachunku, współpraca z marką. Artykuł prasowy, krytyczna opinia lub pytanie na forum NIE są reklamą."),
    2: ("Oceń, czy materiał marketingowy firmy inwestycyjnej NIE SPEŁNIA wymogów art. 44 rozporządzenia "
        "delegowanego 2017/565: informacja o ryzyku musi towarzyszyć informacjom o zyskach, być wyraźna "
        "(czcionka nie mniejsza niż przeważająca, widoczna, nie w przypisie), zrozumiała i w tym samym języku; "
        "wyniki historyczne i prognozy wymagają ostrzeżeń; nie wolno sugerować aprobaty KNF."),
    3: ("Oceń, czy podmiot FAKTYCZNIE oferuje doradztwo inwestycyjne w rozumieniu art. 76 ustawy o obrocie "
        "instrumentami finansowymi: rekomendacje nabycia, zbycia lub trzymania instrumentów finansowych "
        "(akcje, obligacje, jednostki funduszy, ETF, instrumenty pochodne, CFD) przygotowane w oparciu o potrzeby "
        "i sytuację klienta. Edukacja ogólna, doradztwo podatkowe, ubezpieczenia oraz kryptoaktywa NIE są doradztwem "
        "inwestycyjnym w tym rozumieniu."),
}


class LLM:
    def __init__(self):
        self._ok: bool | None = None
        self._checked = 0.0

    def available(self) -> bool:
        if config.LLM_ENGINE == "none":
            return False
        if self._ok is not None and time.time() - self._checked < (60 if self._ok else 10):
            return self._ok
        try:
            if config.LLM_ENGINE == "ollama":
                tags = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json()
                self._ok = any(m["name"] == config.LLM_MODEL or m["name"].split(":")[0] == config.LLM_MODEL
                               for m in tags.get("models", []))
            else:
                self._ok = httpx.get(f"{config.OPENAI_COMPAT_URL}/models", timeout=2).status_code == 200
        except Exception:
            self._ok = False
        self._checked = time.time()
        return self._ok

    def _chat(self, prompt: str) -> str:
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        if config.LLM_ENGINE == "ollama":
            # think=False: modele z trybem rozumowania (Gemma 4) inaczej zużywają limit tokenów przed odpowiedzią
            r = httpx.post(f"{config.OLLAMA_URL}/api/chat", timeout=config.LLM_TIMEOUT, json={
                "model": config.LLM_MODEL, "stream": False, "format": "json", "think": False, "messages": msgs,
                "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 512}})
            r.raise_for_status()
            msg = r.json().get("message", {})
            return msg.get("content") or msg.get("thinking") or ""
        r = httpx.post(f"{config.OPENAI_COMPAT_URL}/chat/completions", timeout=config.LLM_TIMEOUT, json={
            "model": config.LLM_MODEL, "temperature": 0, "messages": msgs,
            "response_format": {"type": "json_object"}})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def review(self, req: LLMReviewRequest) -> LLMReviewResponse:
        if not self.available():
            return LLMReviewResponse(available=False, error="LLM niedostępny")
        prompt = (f"{TASKS[req.module]}\n\nKontekst: {req.context}\n\nMATERIAŁ:\n\"\"\"\n{req.text[:3500]}\n\"\"\"\n\n"
                  'Zwróć JSON: {"probability": liczba od 0 do 1 (prawdopodobieństwo naruszenia), '
                  '"reasons": [2-4 krótkie powody po polsku]}')
        try:
            raw = self._chat(prompt)
            if not raw.strip():
                raise ValueError("pusta odpowiedź modelu")
            m = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(m.group(0) if m else raw)
            p = max(0.0, min(1.0, float(data.get("probability", 0.0))))
            reasons = [str(x)[:300] for x in (data.get("reasons") or [])][:4]
            score = (1 - config.LLM_WEIGHT) * req.rule_score + config.LLM_WEIGHT * p
            return LLMReviewResponse(available=True, probability=round(p, 4), score=round(score, 4),
                                     weight=config.LLM_WEIGHT, reasons=reasons, model=config.LLM_MODEL)
        except Exception as exc:
            log.warning("LLM review failed: %s", exc)
            return LLMReviewResponse(available=True, error=str(exc)[:300], model=config.LLM_MODEL)


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm
