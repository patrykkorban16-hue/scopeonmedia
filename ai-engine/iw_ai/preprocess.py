"""Preprocessing: usuwanie tagów HTML, normalizacja, tokeny, deduplikacja, embedding + bloki z cechami wizualnymi.

Cechy wizualne bloków (rozmiar czcionki, kolor, tło, ukrycie, stopka, sekcja „Legal”, przypisy) są potrzebne
regułom 4–8 Modułu 2. Źródła stylów, w kolejności dokładności:
  1. raport renderowania z Playwright (style obliczone przez przeglądarkę, 3 szerokości ekranu),
  2. statyczna kaskada CSS: arkusze <style> + atrybuty style (prosty silnik selektorów),
  3. sam tekst (posty social media).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

from .embeddings import get_embedder
from .schemas import Block, PreprocessRequest, PreprocessResponse, RenderReport
from .text import (contrast_ratio, content_hash, detect_language, dominant_language, fold, normalize, simhash,
                   tokenize)

DROP_TAGS = ["script", "style", "noscript", "template", "svg", "iframe", "head", "meta", "link"]
CONTAINER = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "blockquote", "figcaption", "div", "section",
             "article", "footer", "header", "aside", "label", "dd", "dt", "caption", "summary", "details", "main",
             "nav", "ul", "ol", "table", "tr", "tbody", "body", "form", "dialog"}
INLINE = {"a", "span", "small", "strong", "em", "b", "i", "u", "sup", "sub", "mark", "font"}
HEADING_PX = {"h1": 32.0, "h2": 24.0, "h3": 18.72, "h4": 16.0, "h5": 13.28, "h6": 10.72}
INHERITED = {"font-size", "color", "font-weight", "visibility"}
LEGAL_RX = re.compile(r"\b(legal|nota[- ]prawna|informacje[- ]prawne|zastrzezenia|disclaimer|regulacje|footnote|przypis)", re.I)


# ============================================================ statyczna kaskada CSS
@dataclass
class CssRule:
    selector: list[list[tuple[str | None, set[str], str | None]]]   # łańcuch potomków; (tag, klasy, id)
    decls: dict[str, str]
    media: str | None = None          # None | "tablet" | "phone"


def _parse_decls(body: str) -> dict[str, str]:
    out = {}
    for part in body.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.replace("!important", "").strip()
    return out


def _parse_selector(sel: str):
    sel = sel.strip()
    if not sel or re.search(r"[:\[~+*]", sel):
        return None                      # pseudo-klasy, atrybuty itp. – poza zakresem prostego silnika
    chain = []
    for comp in sel.replace(">", " ").split():
        m = re.fullmatch(r"([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)(#[\w-]+)?((?:\.[\w-]+)*)", comp)
        if not m:
            return None
        classes = {c for c in (m.group(2) + m.group(4)).split(".") if c}
        chain.append(((m.group(1) or "").lower() or None, classes, m.group(3)[1:] if m.group(3) else None))
    return chain


def parse_stylesheets(soup: BeautifulSoup) -> list[CssRule]:
    rules: list[CssRule] = []
    for st in soup.find_all("style"):
        css = re.sub(r"/\*.*?\*/", "", st.get_text(), flags=re.S)
        # bloki @media (max-width: N) – rozpoznajemy telefon/tablet
        for mm in re.finditer(r"@media[^{]*max-width\s*:\s*(\d+)px[^{]*\{((?:[^{}]*\{[^{}]*\})*)\s*\}", css, re.I):
            width = int(mm.group(1))
            media = "phone" if width <= 600 else ("tablet" if width <= 1024 else None)
            for sm in re.finditer(r"([^{}]+)\{([^{}]*)\}", mm.group(2)):
                for sel in sm.group(1).split(","):
                    chain = _parse_selector(sel)
                    if chain:
                        rules.append(CssRule(chain, _parse_decls(sm.group(2)), media))
        css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", css)
        for sm in re.finditer(r"([^{}@]+)\{([^{}]*)\}", css):
            for sel in sm.group(1).split(","):
                chain = _parse_selector(sel)
                if chain:
                    rules.append(CssRule(chain, _parse_decls(sm.group(2))))
    return rules


def _match_compound(el: Tag, comp) -> bool:
    tag, classes, el_id = comp
    if tag and el.name != tag:
        return False
    if el_id and el.get("id") != el_id:
        return False
    if classes and not classes.issubset(set(el.get("class", []) or [])):
        return False
    return True


def _match(el: Tag, chain) -> bool:
    if not _match_compound(el, chain[-1]):
        return False
    node, idx = el.parent, len(chain) - 2
    while idx >= 0 and isinstance(node, Tag):
        if _match_compound(node, chain[idx]):
            idx -= 1
        node = node.parent
    return idx < 0


def _font_px(value: str, parent_px: float) -> float | None:
    v = value.strip().lower()
    named = {"xx-small": 9, "x-small": 10, "small": 13, "medium": 16, "large": 18, "x-large": 24, "xx-large": 32,
             "smaller": parent_px * 0.83, "larger": parent_px * 1.2}
    if v in named:
        return float(named[v])
    m = re.match(r"([\d.]+)\s*(px|pt|em|rem|%|vw)?", v)
    if not m:
        return None
    n, unit = float(m.group(1)), (m.group(2) or "px")
    return {"px": n, "pt": n * 4 / 3, "em": n * parent_px, "rem": n * 16, "%": n * parent_px / 100, "vw": n * 13.66}[unit]


class StyleEngine:
    def __init__(self, soup: BeautifulSoup):
        self.rules = parse_stylesheets(soup)
        self._cache: dict[tuple[int, str | None], dict] = {}

    def computed(self, el: Tag, media: str | None = None) -> dict:
        key = (id(el), media)
        if key in self._cache:
            return self._cache[key]
        parent = el.parent if isinstance(el.parent, Tag) else None
        ps = self.computed(parent, media) if parent is not None else {
            "font-size": 16.0, "color": "#222222", "font-weight": "400", "visibility": "visible",
            "display": "block", "bg": "#ffffff", "opacity": 1.0, "hidden_reason": None}
        style = {k: ps[k] for k in INHERITED}
        style["bg"] = ps["bg"]
        style["opacity"] = ps["opacity"]
        style["hidden_reason"] = ps["hidden_reason"]
        style["display"] = "block"
        if el.name in HEADING_PX:
            style["font-size"] = HEADING_PX[el.name]
            style["font-weight"] = "700"
        if el.name == "small":
            style["font-size"] = ps["font-size"] * 0.83
        if el.name in {"strong", "b", "th"}:
            style["font-weight"] = "700"
        if el.name in {"sup", "sub"}:
            style["font-size"] = ps["font-size"] * 0.75
        decls: dict[str, str] = {}
        for r in self.rules:
            if (r.media is None or r.media == media or (media == "phone" and r.media == "tablet")) and _match(el, r.selector):
                decls.update(r.decls)
        decls.update(_parse_decls(el.get("style", "") or ""))
        if "font-size" in decls:
            px = _font_px(decls["font-size"], ps["font-size"])
            if px:
                style["font-size"] = px
        if "color" in decls:
            style["color"] = decls["color"]
        for k in ("background-color", "background"):
            if k in decls:
                m = re.search(r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|\b[a-z]+\b)", decls[k])
                if m and m.group(1) not in {"none", "url", "linear"}:
                    style["bg"] = m.group(1)
        if "font-weight" in decls:
            style["font-weight"] = decls["font-weight"]
        if "opacity" in decls:
            try:
                style["opacity"] = ps["opacity"] * float(decls["opacity"])
            except ValueError:
                pass
        if decls.get("display") == "none" or el.has_attr("hidden"):
            style["hidden_reason"] = style["hidden_reason"] or "display_none"
        if decls.get("visibility") == "hidden":
            style["hidden_reason"] = style["hidden_reason"] or "visibility_hidden"
        if el.get("aria-hidden") == "true":
            style["hidden_reason"] = style["hidden_reason"] or "aria_hidden"
        if parent is not None and parent.name == "details" and not parent.has_attr("open") and el.name != "summary":
            style["hidden_reason"] = style["hidden_reason"] or "details_closed"
        if el.name == "dialog" and not el.has_attr("open"):
            style["hidden_reason"] = style["hidden_reason"] or "modal_closed"
        if "overflow" in decls and "hidden" in decls["overflow"] and ("height" in decls or "max-height" in decls):
            style["clipped"] = True
        if decls.get("text-overflow") == "ellipsis":
            style["clipped"] = True
        style["clipped"] = style.get("clipped", False) or ps.get("clipped", False)
        self._cache[key] = style
        return style


# ============================================================ bloki
def _context_flags(el: Tag) -> tuple[bool, bool, bool]:
    footer = legal = footnote = False
    node, depth = el, 0
    while isinstance(node, Tag) and depth < 14:
        ident = " ".join([node.get("id", "") or ""] + list(node.get("class", []) or []))
        if node.name == "footer" or re.search(r"footer|stopka", ident, re.I):
            footer = True
        if LEGAL_RX.search(ident):
            legal = True
        if node.name in {"sup", "sub"} or re.search(r"footnote|przypis", ident, re.I):
            footnote = True
        # sekcja z nagłówkiem „Informacje prawne / Legal”
        if node.name in {"section", "div", "aside"}:
            h = node.find(["h2", "h3", "h4", "strong"], recursive=False)
            if h and LEGAL_RX.search(fold(h.get_text(" ", strip=True)).replace(" ", "-")):
                legal = True
        node = node.parent
        depth += 1
    return footer, legal, footnote


def _blocks_static(html: str) -> tuple[list[Block], bool, bool]:
    soup = BeautifulSoup(html, "lxml")
    engine = StyleEngine(soup)
    viewport_meta = soup.find("meta", attrs={"name": "viewport"}) is not None
    for t in soup(DROP_TAGS):
        t.decompose()
    body = soup.body or soup
    out: list[Block] = []
    seen: set[str] = set()
    has_media = any(r.media for r in engine.rules)

    def emit(el: Tag, raw: str):
        txt = normalize(raw)
        if len(txt) < 2 or txt[:300] in seen:
            return
        seen.add(txt[:300])
        target = el
        for child in el.find_all(INLINE):          # cały tekst w jednym elemencie inline → jego styl
            if normalize(child.get_text(" ", strip=True)) == txt:
                target = child
                break
        st = engine.computed(target)
        footer, legal, footnote = _context_flags(target)
        if re.match(r"^\s*(\*{1,3}|¹|²|³|\(\*\))", txt):
            footnote = True
        hidden_reason = st["hidden_reason"]
        if st["opacity"] < 0.35 and not hidden_reason:
            hidden_reason = "transparent"
        if st["font-size"] < 4 and not hidden_reason:
            hidden_reason = "zero_size"
        vps = {}
        if has_media:
            for media in ("tablet", "phone"):
                ms = engine.computed(target, media)
                vps[media] = {"font_px": round(ms["font-size"], 1), "hidden": bool(ms["hidden_reason"]),
                              "clipped": bool(ms.get("clipped"))}
        weight = str(st["font-weight"])
        out.append(Block(
            i=len(out), text=txt, tag=el.name, font_px=round(st["font-size"], 1), color=st["color"], bg=st["bg"],
            contrast=contrast_ratio(st["color"], st["bg"]) if st["opacity"] >= 0.99 else
            round(contrast_ratio(st["color"], st["bg"]) * st["opacity"], 2),
            bold=weight in {"bold", "bolder"} or (weight.isdigit() and int(weight) >= 600),
            heading=el.name in HEADING_PX or target.name in HEADING_PX, hidden=bool(hidden_reason),
            hidden_reason=hidden_reason, footer=footer, legal=legal, footnote=footnote,
            clipped=bool(st.get("clipped")), viewports=vps,
        ))

    for el in body.find_all(True):
        if el.name not in CONTAINER:
            continue
        if el.find(lambda t: isinstance(t, Tag) and t.name in CONTAINER) is None:
            emit(el, el.get_text(" ", strip=True))
        else:
            loose = " ".join((c if isinstance(c, NavigableString) else c.get_text(" ", strip=True))
                             for c in el.children
                             if isinstance(c, NavigableString) or (isinstance(c, Tag) and c.name in INLINE))
            if loose.strip():
                emit(el, loose)
    return out, viewport_meta, has_media


def _blocks_render(render: RenderReport) -> list[Block]:
    desk = render.viewports.get("desktop") or next(iter(render.viewports.values()))
    by_key = {name: {b.text[:80]: b for b in vp.blocks} for name, vp in render.viewports.items() if name != "desktop"}
    out = []
    seen: set[str] = set()
    for b in desk.blocks:
        txt = normalize(b.text)
        if len(txt) < 2 or txt[:300] in seen:
            continue
        seen.add(txt[:300])
        vps = {}
        for name, idx in by_key.items():
            ob = idx.get(b.text[:80])
            vps[name] = ({"font_px": ob.font_px, "hidden": ob.hidden, "clipped": ob.clipped or render.viewports[name].horizontal_scroll}
                         if ob else {"font_px": None, "hidden": True, "clipped": False})
        out.append(Block(
            i=len(out), text=txt, tag=b.tag, font_px=b.font_px or 16.0, color=b.color or "#222222", bg=b.bg or "#ffffff",
            contrast=contrast_ratio(b.color, b.bg), bold=b.bold, heading=b.tag in HEADING_PX, hidden=b.hidden,
            hidden_reason=b.hidden_reason, footer=b.footer, legal=b.legal, footnote=b.footnote, clipped=b.clipped,
            occluded=b.occluded, pos=min(1.0, b.top / max(b.page_h, 1.0)), viewports=vps,
        ))
    return out


def _blocks_text(text: str) -> list[Block]:
    parts = [normalize(p) for p in re.split(r"\n+", text) if p.strip()]
    return [Block(i=i, text=p, tag="p") for i, p in enumerate(parts)]


def predominant_font(blocks: list[Block]) -> float:
    """Przeważająca wielkość czcionki – ważona długością tekstu (reguła 4)."""
    c: Counter = Counter()
    for b in blocks:
        if not b.hidden and not b.heading:
            c[round(b.font_px)] += len(b.text)
    return float(c.most_common(1)[0][0]) if c else 16.0


# ============================================================ wejście
def preprocess(req: PreprocessRequest) -> PreprocessResponse:
    responsive_checked = False
    viewport_meta = True
    if req.render and req.render.viewports:
        blocks = _blocks_render(req.render)
        source = "render"
        responsive_checked = len(req.render.viewports) > 1
        viewport_meta = req.render.viewport_meta
    elif req.html:
        blocks, viewport_meta, responsive_checked = _blocks_static(req.html)
        source = "static_css"
    else:
        blocks = _blocks_text(req.text or "")
        source = "text"
    if not req.render and blocks:
        n = max(len(blocks) - 1, 1)
        for b in blocks:
            b.pos = round(b.i / n, 3)
    for b in blocks:
        b.language = detect_language(b.text)
    text = "\n".join(b.text for b in blocks if not b.hidden or b.hidden_reason in {"details_closed", "modal_closed"})
    if not text and req.text:
        text = normalize(req.text)
    tokens = tokenize(text)
    emb, model = get_embedder().embed(text)
    lang = dominant_language([(b.language, len(b.text)) for b in blocks if not b.hidden])
    if lang == "und":
        lang = detect_language(text)
    return PreprocessResponse(
        text=text, normalized=" ".join(tokens), tokens=tokens[:2000], token_count=len(tokens),
        content_hash=content_hash(text), simhash=simhash(tokens), language=lang,
        embedding=emb, embedding_model=model, blocks=blocks, style_source=source,
        responsive_checked=responsive_checked, viewport_meta=viewport_meta,
    )


__all__ = ["preprocess", "predominant_font", "fold"]
