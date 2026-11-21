"""Renderowanie stron w Playwright (Chromium): DOM po wykonaniu JS, style obliczone przez przeglądarkę
w trzech szerokościach ekranu (desktop / tablet / telefon) oraz zrzuty ekranu jako materiał dowodowy.

Raport renderowania zasila reguły 4–8 Modułu 2 (czcionka, kontrast, przesłonięcie, ukrycie, responsywność).
Przeglądarka jest utrzymywana per wątek workera (Playwright sync API nie jest współdzielony między wątkami).
"""
from __future__ import annotations

import logging
import threading

from .. import config
from .http import random_ua

log = logging.getLogger(__name__)
VIEWPORTS = {"desktop": (1366, 900), "tablet": (820, 1180), "phone": (390, 844)}

COLLECT_JS = r"""
() => {
  const BLOCK = new Set(['P','LI','H1','H2','H3','H4','H5','H6','TD','TH','BLOCKQUOTE','FIGCAPTION','DIV','SECTION',
    'ARTICLE','FOOTER','HEADER','ASIDE','LABEL','DD','DT','CAPTION','SUMMARY','DETAILS','MAIN','NAV','UL','OL','TABLE','TR','DIALOG']);
  const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','SVG','IFRAME']);
  const LEGAL = /(legal|nota[- ]prawna|informacje[- ]prawne|zastrze|disclaimer|footnote|przypis)/i;
  const RISKY = /(ryzyk|strat|utrat|risk|verlust)/i;
  const H = Math.max(document.documentElement.scrollHeight, 1);
  const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor;
      if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c; } return 'rgb(255, 255, 255)'; };
  const hiddenReason = (el) => {
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.display === 'none') return 'display_none';
      if (s.visibility === 'hidden') return 'visibility_hidden';
      if (e.getAttribute && e.getAttribute('aria-hidden') === 'true') return 'aria_hidden';
      if (e.tagName === 'DETAILS' && !e.open && !el.closest('summary')) return 'details_closed';
      if (e.tagName === 'DIALOG' && !e.open) return 'modal_closed';
      if (parseFloat(s.opacity) < 0.35) return 'transparent';
    }
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return 'zero_size';
    return null;
  };
  const ctx = (el) => { let footer = false, legal = false, footnote = false;
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const ident = (e.id || '') + ' ' + (typeof e.className === 'string' ? e.className : '');
      if (e.tagName === 'FOOTER' || /footer|stopka/i.test(ident)) footer = true;
      if (LEGAL.test(ident)) legal = true;
      if (e.tagName === 'SUP' || e.tagName === 'SUB' || /footnote|przypis/i.test(ident)) footnote = true;
      const h = e.querySelector(':scope > h2, :scope > h3, :scope > h4, :scope > strong');
      if (h && ['SECTION','DIV','ASIDE'].includes(e.tagName) && LEGAL.test((h.textContent||'').replace(/\s+/g,'-'))) legal = true;
    } return {footer, legal, footnote}; };
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (!BLOCK.has(el.tagName) || SKIP.has(el.tagName)) continue;
    if ([...el.children].some(c => BLOCK.has(c.tagName))) continue;
    const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    if (text.length < 2) continue;
    let t = el;   // cały tekst w jednym elemencie inline → jego styl
    while (t.children.length === 1 && (t.children[0].textContent || '').trim() === (t.textContent || '').trim()) t = t.children[0];
    const s = getComputedStyle(t);
    const r = el.getBoundingClientRect();
    const hr = hiddenReason(t);
    let occluded = false;
    if (!hr && RISKY.test(text)) {
      el.scrollIntoView({block: 'center'});
      const rr = el.getBoundingClientRect();
      const top = document.elementFromPoint(rr.left + Math.min(rr.width / 2, 40), rr.top + rr.height / 2);
      occluded = !!top && !el.contains(top) && !top.contains(el);
    }
    const clipped = (el.scrollWidth > el.clientWidth + 2 && ['hidden', 'clip'].includes(s.overflowX)) ||
                    (el.scrollHeight > el.clientHeight + 2 && ['hidden', 'clip'].includes(s.overflowY)) ||
                    (s.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth);
    out.push({text: text.slice(0, 3000), tag: el.tagName.toLowerCase(), font_px: parseFloat(s.fontSize),
      color: s.color, bg: bgOf(t), bold: parseInt(s.fontWeight) >= 600, hidden: !!hr, hidden_reason: hr,
      top: r.top + window.scrollY, page_h: H, clipped, occluded, ...ctx(el)});
  }
  window.scrollTo(0, 0);
  return {blocks: out, horizontal_scroll: document.documentElement.scrollWidth > window.innerWidth + 4,
          viewport_meta: !!document.querySelector('meta[name=viewport]')};
}
"""

_local = threading.local()


def available() -> bool:
    if config.RENDER_MODE == "never":
        return False
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _browser():
    if getattr(_local, "browser", None) is None or not _local.browser.is_connected():
        from playwright.sync_api import sync_playwright

        _local.pw = sync_playwright().start()
        _local.browser = _local.pw.chromium.launch(headless=True)
    return _local.browser


def render(url: str, proxy: str | None = None) -> dict:
    """Zwraca {html, status, render: {viewports, viewport_meta}, screenshots: {desktop, phone} (PNG bytes)}."""
    browser = _browser()
    ctx = browser.new_context(user_agent=random_ua(), locale="pl-PL", viewport={"width": 1366, "height": 900},
                              proxy={"server": proxy} if proxy else None)
    page = ctx.new_page()
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=int(config.REQUEST_TIMEOUT * 1500))
        html = page.content()
        viewports, shots, vp_meta = {}, {}, True
        for name, (w, h) in VIEWPORTS.items():
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(150)
            data = page.evaluate(COLLECT_JS)
            viewports[name] = {"width": w, "blocks": data["blocks"], "horizontal_scroll": data["horizontal_scroll"]}
            vp_meta = data["viewport_meta"]
            if config.SCREENSHOTS and name in ("desktop", "phone"):
                shots[name] = page.screenshot(full_page=True, type="png", clip=None) if page.evaluate(
                    "document.documentElement.scrollHeight") < 6000 else page.screenshot(type="png")
        return {"html": html, "status": resp.status if resp else 200,
                "render": {"viewports": viewports, "viewport_meta": vp_meta}, "screenshots": shots}
    finally:
        ctx.close()
