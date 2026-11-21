"""Reprezentacja wektorowa tekstu.

Domyślnie wielojęzyczny model embeddingów uruchamiany lokalnie w Ollamie (on-premise). Gdy Ollama lub model
są niedostępne, silnik przełącza się na haszowane n-gramy znakowe (odporne na fleksję), żeby pipeline działał dalej.
"""
from __future__ import annotations

import logging
import time

import httpx
import numpy as np

from . import config
from .text import fold

log = logging.getLogger(__name__)


class Embedder:
    def __init__(self):
        from sklearn.feature_extraction.text import HashingVectorizer

        self._hash = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=config.EMBED_DIM_HASHING,
                                       alternate_sign=False, norm="l2")
        self._ollama_ok: bool | None = None
        self._checked = 0.0
        self._proto_cache: dict[tuple[str, int], np.ndarray] = {}

    def _ollama_available(self) -> bool:
        if config.EMBED_ENGINE != "ollama":
            return False
        if self._ollama_ok is not None and time.time() - self._checked < (60 if self._ollama_ok else 10):
            return self._ollama_ok
        try:
            tags = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json()
            names = {m["name"].split(":")[0] for m in tags.get("models", [])}
            self._ollama_ok = config.EMBED_MODEL.split(":")[0] in names
        except Exception:
            self._ollama_ok = False
        self._checked = time.time()
        return self._ollama_ok

    @property
    def model_name(self) -> str:
        return f"ollama:{config.EMBED_MODEL}" if self._ollama_available() else "hashing-char-ngrams"

    def embed_many(self, texts: list[str]) -> tuple[np.ndarray, str]:
        if self._ollama_available():
            try:
                r = httpx.post(f"{config.OLLAMA_URL}/api/embed", timeout=120,
                               json={"model": config.EMBED_MODEL, "input": [t[:4000] for t in texts]})
                r.raise_for_status()
                arr = np.asarray(r.json()["embeddings"], dtype=np.float32)
                arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
                return arr, f"ollama:{config.EMBED_MODEL}"
            except Exception as exc:
                log.warning("embedding przez Ollamę nieudany (%s) – fallback", exc)
                self._ollama_ok = False
        return self._hash.transform([fold(t)[:6000] for t in texts]).toarray().astype(np.float32), "hashing-char-ngrams"

    def embed(self, text: str) -> tuple[list[float], str]:
        arr, model = self.embed_many([text])
        return [round(float(x), 5) for x in arr[0]], model

    def similarity_to(self, emb: list[float], model: str, prototypes: list[str]) -> float:
        """Maks. podobieństwo kosinusowe do tekstów-prototypów (prototypy liczone tym samym modelem)."""
        if not emb:
            return 0.0
        key = (model, hash(tuple(prototypes)))
        if key not in self._proto_cache:
            arr, used = self.embed_many(prototypes)
            if used != model:            # dokument osadzony innym modelem – nie porównujemy przestrzeni
                return 0.0
            self._proto_cache[key] = arr
        v = np.asarray(emb, dtype=np.float32)
        if v.shape[0] != self._proto_cache[key].shape[1]:
            return 0.0
        return float(np.max(self._proto_cache[key] @ v))


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
