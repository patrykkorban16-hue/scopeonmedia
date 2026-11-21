"""Logika biznesowa: agregator łączący wyniki modułów 1, 2 i 3 w ujednolicone obiekty (UnifiedFinding)."""
from __future__ import annotations

import logging
import re
import unicodedata

from . import __version__
from .context import Ctx
from .modules import m1_ecosystem, m2_compliance, m3_shadow
from .registry import registry
from .schemas import AnalyzeRequest, AnalyzeResponse, UnifiedFinding
from .text import fold

log = logging.getLogger(__name__)
MODULES = (m1_ecosystem, m2_compliance, m3_shadow)


def build_context(req: AnalyzeRequest) -> Ctx:
    registry.ensure(req.registry_version)
    d = req.document
    owner, by = registry.owner_of(d.domain, d.author, d.author_url)
    text = req.pre.text
    folded = fold(text)
    display = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()
    return Ctx(doc=d, pre=req.pre, text=text, folded=folded, owner=owner, owner_by=by,
               matches=registry.find(text, folded, d.links), display=display)


def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    ctx = build_context(req)
    findings: list[UnifiedFinding] = []
    for mod in MODULES:
        try:
            f = mod.analyze(ctx)
        except Exception:
            log.exception("moduł %s – błąd dla dokumentu %s", mod.__name__, req.document.id)
            continue
        if f is not None:
            findings.append(f)
    return AnalyzeResponse(document_id=req.document.id, findings=findings,
                           max_score=max((f.score for f in findings), default=0.0), engine_version=__version__)
