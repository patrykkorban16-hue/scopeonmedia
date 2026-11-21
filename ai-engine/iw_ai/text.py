"""Narzędzia tekstowe: normalizacja, tokenizacja, detekcja języka, czytelność, SimHash, kontrast WCAG."""
from __future__ import annotations

import hashlib
import re
import unicodedata

_POLISH_FOLD = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-ząćęłńóśźż0-9%]+", re.I)

STOPWORDS_PL = set("""aby albo ale ani az bardzo bez bo by byc byl byla bylo byly bedzie beda co czy dla do gdy gdzie i ich
ile im ja jak jaki jako je jego jej jest jestem juz kiedy kto ktora ktore ktory ktorych lub ma maja mi mnie moze na nad
nam nas nasz nasza nasze nie nim nic niz o od oraz po pod przez przy sa sie siebie sobie ta tak takze tam te tego tej
ten tu tym u w we wiec wszystko z za ze zeby tylko twoj twoje twoja twoich panstwa""".split())
STOPWORDS_EN = set("""the an and or of in on for with is are was were be been this that these those it its you your
we our they their at by from as not no may can will would should my me i use get have has just but if all so do""".split())
STOPWORDS_DE = set("""der die das und oder nicht ist sind ein eine mit von zu im auf fur sie wir ihr""".split())
_PL_CHARS = re.compile(r"[ąćęłńśźż]")


def fold(text: str) -> str:
    """Postać do dopasowań: NFKC, małe litery, bez polskich znaków, pojedyncze spacje."""
    t = unicodedata.normalize("NFKC", text).translate(_POLISH_FOLD).lower()
    return _WS.sub(" ", t).strip()


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace(" ", " ").replace("​", "").replace("­", "")
    t = re.sub(r"[‘’‚]", "'", t)
    t = re.sub(r"[“”„]", '"', t)
    t = re.sub(r"[–—]", "-", t)
    return _WS.sub(" ", t).strip()


def tokenize(text: str) -> list[str]:
    return [t for t in (x.lower() for x in _TOKEN.findall(text)) if len(t) > 1 and fold(t) not in STOPWORDS_PL]


def detect_language(text: str) -> str:
    words = re.findall(r"[a-z]+", fold(text))
    if len(words) < 3:
        return "und"
    scores = {
        "pl": sum(w in STOPWORDS_PL for w in words),
        "en": sum(w in STOPWORDS_EN for w in words),
        "de": sum(w in STOPWORDS_DE for w in words),
    }
    # słowa z polskimi znakami diakrytycznymi są silnym sygnałem języka polskiego
    scores["pl"] += 0.7 * sum(1 for w in re.findall(r"\w+", text.lower()) if _PL_CHARS.search(w))
    lang, best = max(scores.items(), key=lambda kv: kv[1])
    return lang if best >= 1 else "und"


def dominant_language(parts: list[tuple[str, int]]) -> str:
    """Język przeważający ważony długością tekstu bloków [(język, liczba znaków)]."""
    acc: dict[str, int] = {}
    for lang, n in parts:
        if lang != "und":
            acc[lang] = acc.get(lang, 0) + n
    return max(acc.items(), key=lambda kv: kv[1])[0] if acc else "und"


# ------------------------------------------------------------------ czytelność (reguła 9)
_SENT = re.compile(r"[.!?]+(?:\s|$)")
_SYL = re.compile(r"[aeiouyąęó]+", re.I)


def readability_pl(text: str) -> dict:
    """Indeks FOG-PL (wariant Gunning Fog dla polszczyzny: trudne słowa = ≥4 sylaby)."""
    words = re.findall(r"[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", text)
    if not words:
        return {"fog": 0.0, "words": 0, "avg_sentence": 0.0, "hard_ratio": 0.0}
    sentences = max(1, len(_SENT.findall(text)) or 1)
    hard = sum(1 for w in words if len(_SYL.findall(w)) >= 4)
    asl = len(words) / sentences
    hard_ratio = hard / len(words)
    fog = 0.4 * (asl + 100 * hard_ratio)
    return {"fog": round(fog, 1), "words": len(words), "avg_sentence": round(asl, 1), "hard_ratio": round(hard_ratio, 3)}


# ------------------------------------------------------------------ deduplikacja
def content_hash(text: str) -> str:
    return hashlib.sha256(fold(text).encode("utf-8")).hexdigest()


def simhash(tokens: list[str], bits: int = 64) -> str:
    v = [0] * bits
    shingles = [" ".join(tokens[i:i + 3]) for i in range(max(1, len(tokens) - 2))] if tokens else []
    for sh in shingles:
        h = int.from_bytes(hashlib.blake2b(sh.encode(), digest_size=8).digest(), "big")
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(bits):
        if v[i] > 0:
            out |= 1 << i
    return f"{out:016x}"


# ------------------------------------------------------------------ kolory / kontrast (reguła 5)
_NAMED = {"white": "#ffffff", "black": "#000000", "red": "#ff0000", "gray": "#808080", "grey": "#808080",
          "silver": "#c0c0c0", "lightgray": "#d3d3d3", "lightgrey": "#d3d3d3", "darkgray": "#a9a9a9",
          "gainsboro": "#dcdcdc", "whitesmoke": "#f5f5f5", "yellow": "#ffff00", "navy": "#000080",
          "blue": "#0000ff", "green": "#008000", "orange": "#ffa500", "transparent": "transparent"}


def parse_color(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    v = value.strip().lower()
    v = _NAMED.get(v, v)
    if v == "transparent":
        return (0, 0, 0, 0.0)
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", v)
    if m:
        parts = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
        try:
            r, g, b = (float(p.rstrip("%")) * (2.55 if p.endswith("%") else 1) for p in parts[:3])
            a = float(parts[3].rstrip("%")) / (100 if parts[3].endswith("%") else 1) if len(parts) > 3 else 1.0
            return (r, g, b, a)
        except ValueError:
            return None
    return None


def _lum(c) -> float:
    def ch(x):
        x = x / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast_ratio(fg: str | None, bg: str | None) -> float:
    f, b = parse_color(fg) or (34, 34, 34, 1), parse_color(bg) or (255, 255, 255, 1)
    if b[3] == 0:
        b = (255, 255, 255, 1)
    if f[3] < 1:   # kolor półprzezroczysty – mieszamy z tłem
        f = tuple(f[i] * f[3] + b[i] * (1 - f[3]) for i in range(3)) + (1,)
    l1, l2 = sorted((_lum(f), _lum(b)), reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)
