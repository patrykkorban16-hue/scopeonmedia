"""Funkcje scoringowe.

Każdy moduł buduje wektor cech x (sygnały regułowe z wagami wᵢ + podobieństwo embeddingu do prototypów)
i liczy  rule_score = σ(b + Σ wᵢ·xᵢ)  – prawdopodobieństwo naruszenia w [0,1].
Ocena LLM (jeśli dostępna) jest dokładana asynchronicznie:  score = (1-λ)·rule_score + λ·p_LLM.
Przypisanie do kategorii ryzyka (niskie/średnie/wysokie) wykonuje backend względem progu z Panelu Kalibracji.
"""
from __future__ import annotations

import math
import re

from .schemas import Reason
from .text import fold

# bazowe podobieństwo „niepowiązanego” tekstu dla danej przestrzeni embeddingów
SEM_BASELINE = {"hashing-char-ngrams": 0.25}
SEM_BASELINE_NEURAL = 0.45


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def semantic_feature(sim: float, model: str, scale: float = 4.0) -> float:
    if sim <= 0:
        return 0.0
    base = SEM_BASELINE.get(model, SEM_BASELINE_NEURAL)
    return max(-1.0, min(1.5, scale * (sim - base)))


def compile_patterns(spec: list[tuple[str, str, float]]) -> list[tuple[str, re.Pattern, float]]:
    """spec: (etykieta, wyrażenie regularne na tekście znormalizowanym 'fold' (bez polskich znaków), waga)."""
    return [(label, re.compile(rx, re.I), w) for label, rx, w in spec]


def find_hits(patterns, folded: str, prefix: str, per_rule: int = 1, display: str | None = None) -> list[Reason]:
    """Dopasowania na tekście znormalizowanym; dowód cytowany z oryginału (`display`), gdy indeksy się zgadzają."""
    src = display if display is not None and len(display) == len(folded) else folded
    hits = []
    for label, rx, w in patterns:
        for i, m in enumerate(rx.finditer(folded)):
            if i >= per_rule:
                break
            s, e = max(0, m.start() - 70), min(len(folded), m.end() + 70)
            hits.append(Reason(rule=f"{prefix}:{label}", label=label, evidence=src[s:e].strip(), weight=w))
    return hits


def excerpt_around(text: str, needle: str | None, width: int = 420) -> str:
    if not needle:
        return text[:width].strip() + ("…" if len(text) > width else "")
    f = fold(text)
    i = f.find(fold(needle)[:40])
    if i < 0:
        return text[:width].strip() + ("…" if len(text) > width else "")
    s = max(0, i - width // 3)
    return ("…" if s else "") + text[s:s + width].strip() + ("…" if s + width < len(text) else "")
