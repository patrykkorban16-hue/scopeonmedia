"""Kontekst dokumentu przekazywany do modułów analitycznych."""
from __future__ import annotations

from dataclasses import dataclass, field

from .registry import Entity, Match
from .schemas import Block, DocumentMeta, PreprocessResponse

SOCIAL = {"facebook", "instagram", "tiktok", "youtube", "x", "linkedin"}


@dataclass
class Ctx:
    doc: DocumentMeta
    pre: PreprocessResponse
    text: str
    folded: str
    owner: Entity | None
    owner_by: str | None
    matches: list[Match] = field(default_factory=list)
    display: str = ""          # tekst oryginalny po tej samej normalizacji odstępów co `folded` (te same indeksy)

    def quote(self, start: int, end: int) -> str:
        """Cytat z oryginalnego tekstu (z polskimi znakami) dla zakresu dopasowania w `folded`."""
        src = self.display if len(self.display) == len(self.folded) else self.folded
        return src[max(0, start):max(0, end)].strip()

    @property
    def blocks(self) -> list[Block]:
        return self.pre.blocks

    @property
    def is_social(self) -> bool:
        return self.doc.source_type in SOCIAL

    @property
    def is_polish(self) -> bool:
        return self.pre.language in {"pl", "und"}
