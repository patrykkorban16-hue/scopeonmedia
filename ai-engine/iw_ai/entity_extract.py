"""Ekstrakcja danych podmiotu z treści (Moduł 3: „dane podmiotu”): nazwa, NIP, KRS, REGON, e-mail, telefon, adres."""
from __future__ import annotations

import re

from .schemas import EntityData

NIP_RX = re.compile(r"\bNIP[:\s]*((?:\d[\s-]?){9}\d)\b", re.I)
KRS_RX = re.compile(r"\bKRS[:\s]*(\d{10})\b", re.I)
REGON_RX = re.compile(r"\bREGON[:\s]*(\d{9}(?:\d{5})?)\b", re.I)
EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE_RX = re.compile(r"(?:tel\.?|telefon|phone)[:\s]*((?:\+?48[\s-]?)?(?:\d[\s-]?){8}\d)", re.I)
ADDRESS_RX = re.compile(r"((?:ul\.|al\.|pl\.)\s?[A-ZŁŚŻŹĆ][\w\s.-]{2,40}\d+[\w/]*,?\s*\d{2}-\d{3}\s+[A-ZŁŚŻŹĆ][a-ząćęłńóśźż]+)")
LEGAL_NAME_RX = re.compile(
    r"([A-ZŁŚŻŹĆ0-9][\w&.\- ]{2,60}?\s(?:sp\.\s?z\s?o\.\s?o\.|S\.A\.|spółka akcyjna|sp\. k\.|Sp\. z o\.o\.|Ltd\.?|GmbH|AG))")


def _uniq(xs, limit=5):
    out = []
    for x in xs:
        x = re.sub(r"\s+", " ", x).strip()
        if x and x not in out:
            out.append(x)
    return out[:limit]


def _valid_nip(nip: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", nip)]
    if len(d) != 10:
        return False
    w = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    return sum(a * b for a, b in zip(w, d[:9], strict=True)) % 11 == d[9]


def extract_entity(text: str, fallback_name: str | None) -> EntityData:
    legal = _uniq(LEGAL_NAME_RX.findall(text), 3)
    return EntityData(
        name=legal[0] if legal else fallback_name,
        nip=[n for n in _uniq(re.sub(r"\D", "", m) for m in NIP_RX.findall(text)) if _valid_nip(n)] or
            _uniq(re.sub(r"\D", "", m) for m in NIP_RX.findall(text)),
        krs=_uniq(KRS_RX.findall(text)),
        regon=_uniq(REGON_RX.findall(text)),
        emails=_uniq(EMAIL_RX.findall(text)),
        phones=_uniq(PHONE_RX.findall(text)),
        addresses=_uniq(ADDRESS_RX.findall(text), 3),
    )
