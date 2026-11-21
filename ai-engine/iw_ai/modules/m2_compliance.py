"""Moduł 2 – Weryfikacja zgodności i informacji o ryzyku.

Zakres: materiały marketingowe publikowane bezpośrednio przez firmy inwestycyjne z rejestru (domy maklerskie,
banki prowadzące działalność maklerską, oddziały i firmy transgraniczne).
Lista wymogów: „InvestWatch – kryteria oceny informacji o ryzyku” (reguły 1–18, art. 24 ust. 3 MiFID II,
art. 44 rozporządzenia delegowanego 2017/565). Każda reguła zwraca status pass / fail / warn / na z dowodem.
"""
from __future__ import annotations

import re

from ..context import Ctx
from ..embeddings import get_embedder
from ..preprocess import predominant_font
from ..schemas import Block, Reason, RuleResult, UnifiedFinding
from ..scoring import excerpt_around, semantic_feature, sigmoid
from ..text import fold, readability_pl

BASIS = "rozp. del. 2017/565 art. 44"
RULES = {
    "1": ("Identyfikacja firmy", f"{BASIS} ust. 2 lit. a"),
    "2": ("Oznaczenie reklamy", "art. 24 ust. 3 MiFID II"),
    "3": ("Informacja o ryzyku przy zyskach", f"{BASIS} ust. 2 lit. b"),
    "4": ("Rozmiar czcionki ryzyka", f"{BASIS} ust. 2 lit. c"),
    "5": ("Ekspozycja i kontrast ryzyka", f"{BASIS} ust. 2 lit. c i e"),
    "6": ("Zakrywanie / ukrywanie ryzyka", f"{BASIS} ust. 2 lit. e"),
    "7": ("Dostępność za 1 kliknięciem", f"{BASIS} ust. 2 lit. b i e"),
    "8": ("Responsywność (różne urządzenia)", f"{BASIS} ust. 2 lit. g"),
    "9": ("Zrozumiałość dla grupy docelowej", f"{BASIS} ust. 2 lit. d"),
    "10": ("Spójność językowa", f"{BASIS} ust. 2 lit. f"),
    "11": ("Porównania produktów / usług", f"{BASIS} ust. 3"),
    "12a": ("Wyniki historyczne – okres i zakres", f"{BASIS} ust. 4"),
    "12b": ("Wyniki historyczne – warunki i waluta", f"{BASIS} ust. 4"),
    "13": ("Dominacja wyników historycznych", f"{BASIS} ust. 4 lit. a"),
    "14": ("Ostrzeżenie przy wynikach historycznych", f"{BASIS} ust. 4 lit. d"),
    "15": ("Prognozy przyszłych wyników", f"{BASIS} ust. 6"),
    "16": ("Informacja podatkowa", f"{BASIS} ust. 7"),
    "17": ("Zakaz sugerowania aprobaty organu nadzoru", f"{BASIS} ust. 8"),
    "18": ("Nadzór jako argument bezpieczeństwa", f"{BASIS} ust. 8"),
}

# --------------------------------------------------------------- wzorce (tekst po fold(): bez polskich znaków)
CLAIMS_RX = re.compile(r"\bbez (zadnego )?ryzyka\b|zero ryzyka|wolne od ryzyka|ryzyko (jest )?zerowe|"
                       r"gwarant\w* (zysk|zwrot|dochod|stop)\w*|zysk\w* gwarantowan\w*|pewn\w* (zysk|zarobek|dochod)|"
                       r"100 ?% bezpieczn\w*|calkowicie bezpieczn\w*|nic nie ryzykujesz", re.I)
RISK_RX = re.compile(r"ryzyk\w*|utrat\w*|\bstrat\w*|nie (gwarantuj|stanowi\w* gwarancj|sa gwarancj|jest gwarantowan)\w*|"
                     r"moze (spasc|zmalec|ulec obnizeniu|stracic)|mozesz stracic|wartosc \w+( \w+)? moze|"
                     r"(capital|money) (is )?at risk|you (may|can) lose|risk of loss|verlustrisiko", re.I)
PROFIT_RX = re.compile(r"zysk\w*|zarob\w*|zarabia\w*|zwrot\w*|stop\w* zwrotu|rentown\w*|dochod\w*|oprocentowan\w*|"
                       r"\d+(,\d+)? ?% (rocznie|w skali roku|zysku|zwrotu|w (miesiac|rok|tydzien))|pomnoz\w*|"
                       r"\+ ?\d+(,\d+)? ?%|wzrost\w* (wartosci|o \d)", re.I)
CFD_RX = re.compile(r"\bcfd\b|kontrakt\w* na roznic\w*|dzwigni\w* finansow\w*|\bforex\b", re.I)
CFD_WARN_RX = re.compile(r"\d{1,2}(,\d+)? ?% rachunk\w* (inwestorow )?detaliczn\w*.{0,90}(strat|traci)", re.I)
LABEL_RX = re.compile(r"\breklam\w*|material\w* (reklamow|marketingow|promocyjn)\w*|komunikat\w* (marketingow|reklamow)\w*|"
                      r"informacj\w* (reklamow|marketingow)\w*|#ad\b|sponsorowan\w*|charakter (reklamowy|marketingowy)|"
                      r"tresc promocyjn\w*", re.I)
CLICK_LINK_RX = re.compile(r"ryzyk|ostrzezen|ujawnien|risk", re.I)
JARGON = [r"instrument\w* pochodn", r"depozyt\w* zabezpieczajac", "lewar", "dzwigni", "margin call", "spread",
          "wolumen", "zmiennosc", "ekspozycj", "kontrahent", "rolowan", r"punkt\w* swap", "volatility"]
COMPARE_RX = re.compile(r"w porownaniu|lepsz\w* niz|wiecej niz|nizsz\w* niz|tansz\w* niz|wyzsz\w* niz|"
                        r"\d+ ?(razy|x) (wiecej|wyzej|lepiej)|najnizsz\w* (prowizj|oplat|koszt)\w*|"
                        r"najlepsz\w* (broker|oferta|fundusz|rachunek|platforma)\w*|bije (na glowe|konkurencj)\w*|"
                        r"niz (lokata|lokaty|konto oszczednosciowe|inflacja|obligacje skarbowe)|\bvs\.? ", re.I)
SOURCE_RX = re.compile(r"zrodl\w*:|zrodlo danych|wedlug (danych|raportu|rankingu)|na podstawie (danych|tabeli|cennik)|"
                       r"dane (z|za|wg)\b|stan na \d|przy zalozeniu|zalozeni\w*:", re.I)
PAST_RX = re.compile(r"(stop\w* zwrotu|wynik\w*|zysk\w*|zarobil\w*|wzrosl\w*|urosl\w*|zyskal\w*|przyni(osl|ol)\w*|"
                     r"klienci zarobili)[^.\n]{0,60}\+?\d+(,\d+)? ?%[^.\n]{0,60}"
                     r"(w (ostatni|zeszl|minion|ubieg)\w*|w (roku )?20\d\d|od (poczatku|startu|utworzenia)|"
                     r"za (rok|\d+ lat)|r/r|rok do roku|w ciagu|w \d+ (miesi|lat|tyg))"
                     r"|20\d\d ?(r\.|rok\w*)?:? ?\+?\d+(,\d+)? ?%", re.I)
PAST_DISCLAIMER_RX = re.compile(r"(historyczn|przeszl|osiagniet|dotychczasow)\w* (wyniki|stopy zwrotu|rezultaty)\w*"
                                r".{0,60}(nie (gwarantuj|stanowi|sa|musza|jest)|nie moga)", re.I)
SHORT_PERIOD_RX = re.compile(r"w (ostatni\w* |ciagu )?(miesiac|tydzien|tygodni|kwartal|\d+ (miesiac|tygodn|dni))\w*|"
                             r"w (jeden |1 )?(miesiac|tydzien)|od poczatku roku|\bytd\b|w \d+ (miesiac|dni)\w*", re.I)
FIVE_YEARS_RX = re.compile(r"(5|piec|pieciu) (lat|letni)|ostatnich (5|pieciu)|od (poczatku dzialalnosci|utworzenia|startu funduszu)", re.I)
FEES_RX = re.compile(r"oplat\w*|prowizj\w*|koszt\w*|obciazen\w*", re.I)
FX_RX = re.compile(r"\b(usd|eur|chf|gbp|dolar\w*|euro|frank\w*|funt\w*)\b|walut\w* obc", re.I)
FX_WARN_RX = re.compile(r"kurs\w* walut|ryzyk\w* walutow|zmian\w* kurs", re.I)
FORECAST_RX = re.compile(r"prognoz\w*|przewidujemy|spodziewan\w* (zysk|zwrot|stop|wynik)\w*|oczekiwan\w* (zysk|zwrot|stop|wynik)\w*|"
                         r"potencjal\w* wzrostu|moze przyniesc (nawet )?\d|w ciagu \d+ lat (zyskasz|zarobisz|pomnozysz)|"
                         r"zarobisz|osiagniesz|(twoj|twoje) (kapital|oszczednosci) (wzrosn|urosn|podwoi)\w*|"
                         r"symulacj\w* (zysk|wynik)", re.I)
FORECAST_WARN_RX = re.compile(r"prognoz\w*.{0,60}(nie (sa|jest|stanowi|moga)).{0,40}(wiarygodn|wskaznik|gwarancj)|"
                              r"nie (jest|sa) (wiarygodnym )?wskaznikiem przyszlych", re.I)
TAX_RX = re.compile(r"podat\w*|belki|ulg\w* podatkow\w*|zwolnion\w* z podatku|zwolnien\w* z podatku|\bpit\b|"
                    r"bez podatku|odliczy\w* od (dochodu|podatku)", re.I)
TAX_INDIV_RX = re.compile(r"indywidualn\w* sytuacj\w*", re.I)
TAX_CHANGE_RX = re.compile(r"(moze|moga|mogace) (ulec|podlegac) zmian\w*|zmian\w* przepis", re.I)
KNF_RX = re.compile(r"\bknf\b|komisj\w* nadzoru finansowego|organ\w* nadzoru|\besma\b", re.I)
APPROVAL_RX = re.compile(r"(zatwierdz|zaakceptowan|rekomendowan|polecan|certyfikowan|aprobowan|gwarantowan)\w* (przez )?"
                         r"(knf|komisj\w* nadzoru|esma)|(knf|komisja nadzoru finansowego) (zatwierdzil|zaakceptowal|"
                         r"rekomenduje|poleca|gwarantuje|certyfikuje|aprobuje)\w*|(aprobat|certyfikat|znak jakosci)\w* knf", re.I)
SAFETY_RX = re.compile(r"bezpieczn\w*|gwarant\w*|pewn\w*|bez ryzyka|chronion\w*|nic nie ryzykujesz|spokojn\w*", re.I)
NON_MARKETING_TITLE = re.compile(r"regulamin|polityka prywatnosci|cookies|tabela oplat|kontakt|kariera|praca", re.I)


def _vis(b: Block) -> bool:
    return not b.hidden


def _prom(b: Block) -> float:
    p = b.font_px * (1.6 if b.heading else 1.0) * (1.15 if b.bold else 1.0)
    if b.hidden:
        p *= 0.2
    return p


def _r(rid: str, status: str, weight: float = 0.0, evidence: str | None = None) -> RuleResult:
    name, basis = RULES[rid]
    return RuleResult(id=rid, name=name, status=status, weight=weight if status in {"fail", "warn"} else 0.0,
                      evidence=(evidence or None) and evidence[:400], basis=basis)


def _risk_blocks(blocks: list[Block]) -> list[Block]:
    out = []
    for b in blocks:
        f = CLAIMS_RX.sub(" ", fold(b.text))     # „bez ryzyka” to obietnica, nie ostrzeżenie
        if RISK_RX.search(f):
            out.append(b)
    return out


def evaluate_rules(ctx: Ctx) -> tuple[list[RuleResult], dict]:
    blocks = ctx.blocks
    F = ctx.folded
    ent = ctx.owner
    rules: list[RuleResult] = []
    body_px = predominant_font(blocks)
    risk = _risk_blocks(blocks)
    risk_vis = [b for b in risk if _vis(b)]
    profit = [b for b in blocks if _vis(b) and PROFIT_RX.search(fold(b.text)) and not RISK_RX.search(fold(b.text))]
    best_risk = max(risk_vis, key=_prom) if risk_vis else (max(risk, key=_prom) if risk else None)
    past_blocks = [b for b in blocks if PAST_RX.search(fold(b.text))]
    past_any = bool(past_blocks) or bool(PAST_RX.search(F))

    # 1 identyfikacja firmy
    compact = lambda s: re.sub(r"[\s.,\"']", "", fold(s))
    if ent and compact(ent.name) in compact(F):
        rules.append(_r("1", "pass", evidence=ent.name))
    else:
        rules.append(_r("1", "fail", 1.0, f"brak oficjalnej nazwy firmy „{ent.name if ent else '?'}” w materiale"))

    # 2 oznaczenie reklamy
    m = LABEL_RX.search(F)
    rules.append(_r("2", "pass", evidence=m.group(0)) if m else
                 _r("2", "fail", 0.8, "materiał nie jest oznaczony jako reklamowy/marketingowy"))

    # 3 informacja o ryzyku przy zyskach (+ twierdzenia o braku ryzyka, standardowe ostrzeżenie CFD)
    problems, w3 = [], 0.0
    claims = CLAIMS_RX.search(F)
    q = lambda m: ctx.quote(m.start(), m.end())            # cytat z oryginału (z polskimi znakami)
    if claims:
        problems.append(f"twierdzenie o braku ryzyka / gwarancji zysku: „{q(claims)}”")
        w3 += 2.2
    if profit:
        if not risk:
            problems.append(f"zyski bez informacji o ryzyku: „{profit[0].text[:120]}”")
            w3 += 2.4
        else:
            near = []
            for pb in profit:
                window = [b for b in blocks if abs(b.i - pb.i) <= 2 and _vis(b) and not b.footnote and not b.legal]
                near.append(any(b in risk for b in window) or pb in risk)
            if not any(near):
                problems.append("informacja o ryzyku nie towarzyszy bezpośrednio informacji o zyskach")
                w3 += 1.4
    if CFD_RX.search(F) and not CFD_WARN_RX.search(F):
        problems.append("CFD/dźwignia bez standardowego ostrzeżenia z % rachunków detalicznych tracących środki")
        w3 += 1.6
    if problems:
        rules.append(_r("3", "fail", min(w3, 3.6), "; ".join(problems)))
    elif profit or risk:
        rules.append(_r("3", "pass", evidence=best_risk.text if best_risk else None))
    else:
        rules.append(_r("3", "na", evidence="brak twierdzeń o zyskach"))

    # 4 rozmiar czcionki
    if best_risk is None:
        rules.append(_r("4", "na", evidence="brak informacji o ryzyku do oceny"))
    else:
        ratio = best_risk.font_px / body_px
        ev = f"ryzyko {best_risk.font_px:.0f}px vs przeważająca {body_px:.0f}px (×{ratio:.2f})"
        rules.append(_r("4", "fail", 1.6, ev) if ratio < 0.9 else _r("4", "pass", evidence=ev))

    # 5 ekspozycja i kontrast
    if best_risk is None:
        rules.append(_r("5", "na"))
    else:
        ev = f"kontrast {best_risk.contrast:.1f}:1 ({best_risk.color} na {best_risk.bg})"
        if best_risk.occluded:
            rules.append(_r("5", "fail", 1.6, "informacja o ryzyku przesłonięta innym elementem; " + ev))
        elif best_risk.contrast < 3.0:
            rules.append(_r("5", "fail", 1.8, ev + " – poniżej 3:1"))
        elif best_risk.contrast < 4.5:
            rules.append(_r("5", "fail", 1.1, ev + " – poniżej WCAG AA 4,5:1"))
        else:
            rules.append(_r("5", "pass", evidence=ev))

    # 6 zakrywanie / ukrywanie (przypisy, sekcja Legal, stopka, dół strony)
    if not risk_vis:
        rules.append(_r("6", "na" if not risk else "fail", 1.6 if risk else 0.0,
                        None if not risk else "całość informacji o ryzyku niewidoczna"))
    else:
        def low_vis(b: Block) -> bool:
            return b.footnote or b.legal or (b.footer and b.pos > 0.7) or (b.pos > 0.9 and b.font_px < body_px)
        if all(low_vis(b) for b in risk_vis):
            where = ", ".join(sorted({k for b in risk_vis for k, v in
                                      (("przypis", b.footnote), ("sekcja Legal", b.legal), ("stopka", b.footer)) if v})) or "koniec strony"
            rules.append(_r("6", "fail", 1.6, f"ryzyko wyłącznie w miejscu o niskiej widoczności ({where}): „{risk_vis[0].text[:150]}”"))
        else:
            rules.append(_r("6", "pass"))

    # 7 dostępność bez dodatkowej akcji
    hidden_risk = [b for b in risk if b.hidden]
    links_to_risk = [l for l in ctx.doc.links if CLICK_LINK_RX.search(fold(l))]
    if risk_vis:
        rules.append(_r("7", "pass"))
    elif hidden_risk:
        rules.append(_r("7", "fail", 1.6, f"ryzyko widoczne dopiero po rozwinięciu/kliknięciu ({hidden_risk[0].hidden_reason})"))
    elif links_to_risk and profit:
        rules.append(_r("7", "fail", 1.4, f"informacja o ryzyku tylko pod linkiem: {links_to_risk[0]}"))
    else:
        rules.append(_r("7", "na"))

    # 8 responsywność
    if best_risk is None:
        rules.append(_r("8", "na"))
    elif ctx.pre.responsive_checked:
        issues, w8 = [], 1.2
        for b in risk:
            for vp, v in b.viewports.items():
                if v.get("hidden") and not b.hidden:
                    issues.append(f"{vp}: ostrzeżenie ukryte")
                    w8 = 2.0
                elif v.get("clipped"):
                    issues.append(f"{vp}: tekst ucięty")
                elif v.get("font_px") and v["font_px"] < 10 <= b.font_px:   # degradacja względem desktopu
                    issues.append(f"{vp}: czcionka {v['font_px']:.0f}px")
        if not ctx.pre.viewport_meta:
            issues.append("brak meta viewport – strona skalowana na telefonie")
        rules.append(_r("8", "fail", w8, "; ".join(sorted(set(issues)))) if issues else
                     _r("8", "pass", evidence="sprawdzono: " + ", ".join(sorted({vp for b in risk for vp in b.viewports})) or "brak różnic"))
    elif not ctx.pre.viewport_meta and ctx.pre.style_source != "text":
        rules.append(_r("8", "warn", 0.6, "brak meta viewport – na telefonie tekst może być skalowany poniżej czytelności"))
    else:
        rules.append(_r("8", "na", evidence="nie zweryfikowano (brak renderowania i reguł @media)"))

    # 9 zrozumiałość
    if not risk_vis:
        rules.append(_r("9", "na"))
    else:
        rt = " ".join(b.text for b in risk_vis)
        rd = readability_pl(rt)
        jargon = [j.replace("\\w*", "") for j in JARGON if re.search(j, fold(rt))]
        ev = f"FOG-PL {rd['fog']} (śr. zdanie {rd['avg_sentence']} słów, trudne słowa {rd['hard_ratio']:.0%})"
        if jargon:
            ev += f"; żargon: {', '.join(jargon)}"
        # progi FOG-PL dla polszczyzny (długie wyrazy są normą): >17 trudny, >21 specjalistyczny
        if rd["fog"] > 21 or len(jargon) >= 4:
            rules.append(_r("9", "fail", 0.8, ev))
        elif rd["fog"] > 17 or len(jargon) >= 2:
            rules.append(_r("9", "warn", 0.8, ev))
        else:
            rules.append(_r("9", "pass", evidence=ev))

    # 10 spójność językowa
    main = ctx.pre.language
    if not risk_vis or main == "und":
        rules.append(_r("10", "na"))
    else:
        langs = {b.language for b in risk_vis if b.language != "und"}
        if langs and main not in langs:
            rules.append(_r("10", "fail", 1.6, f"przekaz w języku „{main}”, ostrzeżenie w „{', '.join(sorted(langs))}”: „{risk_vis[0].text[:120]}”"))
        else:
            rules.append(_r("10", "pass", evidence=f"język: {main}"))

    # 11 porównania
    cm = COMPARE_RX.search(F)
    if not cm:
        rules.append(_r("11", "na"))
    elif SOURCE_RX.search(F):
        rules.append(_r("11", "pass", evidence=f"porównanie „{q(cm)}” – podano źródło/założenia"))
    else:
        rules.append(_r("11", "fail", 1.3, f"porównanie bez źródła i założeń: „{q(cm)}”"))

    # 12a / 12b / 13 / 14 wyniki historyczne
    if not past_any:
        for rid in ("12a", "12b", "13", "14"):
            rules.append(_r(rid, "na"))
    else:
        pm = PAST_RX.search(F)
        missing = []
        years = set(re.findall(r"20\d\d", F))
        if SHORT_PERIOD_RX.search(pm.group(0) if pm else F):
            missing.append("okres krótszy niż pełne 12 miesięcy")
        if not FIVE_YEARS_RX.search(F) and len(years) < 5:
            missing.append("brak danych za ostatnie 5 lat")
        if not years and not re.search(r"\d{2}\.\d{2}\.\d{4}", F):
            missing.append("brak okresu referencyjnego")
        if not re.search(r"zrodl\w*", F):
            missing.append("brak źródła danych")
        heavy = [x for x in missing if not x.startswith("brak źródła")]
        rules.append(_r("12a", "fail" if heavy else ("warn" if missing else "pass"), 1.2, "; ".join(missing) or None))
        m12b = []
        if not FEES_RX.search(F):
            m12b.append("brak informacji o wpływie opłat i prowizji")
        if FX_RX.search(F) and not FX_WARN_RX.search(F):
            m12b.append("waluta obca bez ostrzeżenia o wpływie kursów walut")
        rules.append(_r("12b", "fail" if m12b else "pass", 0.9, "; ".join(m12b) or None))
        vis_blocks = [b for b in blocks if _vis(b)]
        top = max(vis_blocks, key=_prom) if vis_blocks else None
        if top is not None and top in past_blocks:
            rules.append(_r("13", "fail", 1.3, f"wyniki historyczne są najbardziej eksponowanym elementem: „{top.text[:120]}”"))
        else:
            rules.append(_r("13", "pass"))
        dm = PAST_DISCLAIMER_RX.search(F)
        rules.append(_r("14", "pass", evidence=dm.group(0)) if dm else
                     _r("14", "fail", 1.8, "brak zastrzeżenia, że wyniki historyczne nie są wiarygodnym wskaźnikiem przyszłych wyników"))

    # 15 prognozy
    fm = FORECAST_RX.search(F)
    if not fm:
        rules.append(_r("15", "na"))
    elif FORECAST_WARN_RX.search(F):
        rules.append(_r("15", "warn", 0.3, f"wykryto prognozę: „{q(fm)}” (z ostrzeżeniem)"))
    else:
        rules.append(_r("15", "fail", 1.4, f"prognoza bez ostrzeżenia: „{q(fm)}”"))

    # 16 informacja podatkowa
    tm = TAX_RX.search(F)
    if not tm:
        rules.append(_r("16", "na"))
    else:
        miss = []
        if not TAX_INDIV_RX.search(F):
            miss.append("brak informacji, że traktowanie podatkowe zależy od indywidualnej sytuacji klienta")
        if not TAX_CHANGE_RX.search(F):
            miss.append("brak informacji o możliwości zmian")
        rules.append(_r("16", "fail", 1.0, f"„{q(tm)}”: " + "; ".join(miss)) if miss else _r("16", "pass"))

    # 17 aprobata organu nadzoru
    am = APPROVAL_RX.search(F)
    rules.append(_r("17", "fail", 2.0, f"sugerowanie aprobaty organu nadzoru: „{q(am)}”") if am else
                 _r("17", "pass" if KNF_RX.search(F) else "na"))

    # 18 nadzór jako argument bezpieczeństwa
    hit = None
    pos = 0
    for sentence in re.split(r"(?<=[.!?])\s+|\n", F):     # odwołanie do nadzoru i „bezpieczeństwo” w jednym zdaniu
        start = F.find(sentence, pos)
        pos = max(pos, start + len(sentence))
        if KNF_RX.search(sentence) and SAFETY_RX.search(sentence) and not RISK_RX.search(CLAIMS_RX.sub(" ", sentence)):
            hit = ctx.quote(start, start + len(sentence))
            break
    rules.append(_r("18", "fail", 2.2, f"„{hit}”") if hit else _r("18", "pass" if KNF_RX.search(F) else "na"))

    meta = {"predominant_font_px": body_px, "risk_blocks": len(risk), "risk_visible": len(risk_vis),
            "profit_blocks": len(profit), "past_performance": past_any, "forecast": bool(fm),
            "style_source": ctx.pre.style_source, "responsive_checked": ctx.pre.responsive_checked,
            "risk_samples": [{"text": b.text[:200], "font_px": b.font_px, "contrast": b.contrast, "hidden": b.hidden_reason,
                              "footer": b.footer, "legal": b.legal, "footnote": b.footnote, "language": b.language}
                             for b in risk[:5]]}
    return rules, meta


PROTOTYPES = ["zyski nawet kilkaset procent rocznie inwestuj z nami bez ryzyka gwarantowany zwrot",
              "nasza inwestycja jest w pełni bezpieczna spełniamy wymogi nadzorcze",
              "wyniki historyczne fundusz wzrósł o kilkadziesiąt procent w ostatnim roku"]


def analyze(ctx: Ctx) -> UnifiedFinding | None:
    ent = ctx.owner
    if ent is None or not ent.is_investment_firm:
        return None
    if NON_MARKETING_TITLE.search(fold(ctx.doc.title or "")):
        return None
    rules, meta = evaluate_rules(ctx)
    sim = get_embedder().similarity_to(ctx.pre.embedding, ctx.pre.embedding_model, PROTOTYPES)
    fails = [r for r in rules if r.status == "fail"]
    warns = [r for r in rules if r.status == "warn"]
    # bias dobrany tak, by jedno wyraźne naruszenie wymogu o wadze ≥1,6 dawało ~0,5 (próg domyślny)
    z = -1.6 + sum(r.weight for r in fails) + 0.4 * sum(r.weight for r in warns) + 0.25 * semantic_feature(sim, ctx.pre.embedding_model)
    rule_score = sigmoid(z)
    top = max(fails, key=lambda r: r.weight) if fails else None
    reasons = [Reason(rule=f"R{r.id}", label=r.name, evidence=r.evidence, weight=r.weight) for r in fails + warns]
    return UnifiedFinding(
        module=2, module_name="Zgodność i informacja o ryzyku",
        category=f"R{top.id} {top.name}" if top else "zgodny",
        score=round(rule_score, 4), rule_score=round(rule_score, 4),
        firm={"id": ent.id, "name": ent.name, "category": ent.category, "country": ent.country,
              "register_id": ent.register_id, "authorized": ent.authorized, "matched_by": ctx.owner_by},
        advertiser={"name": ent.name, "url": ctx.doc.author_url or f"https://{ctx.doc.domain}", "platform": ctx.doc.source_type,
                    "is_labeled_ad": any(r.id == "2" and r.status == "pass" for r in rules)},
        excerpt=excerpt_around(ctx.text, (top.evidence or "") if top else None),
        reasons=reasons, rules=rules,
        details={**meta, "violations": len(fails), "warnings": len(warns), "semantic_similarity": round(sim, 3),
                 "linear_term": round(z, 3)},
        # LLM widzi tylko tekst, a reguły 4–8 dotyczą prezentacji wizualnej → bez automatycznej oceny LLM;
        # analityk może poprosić o opinię doradczą (nie zmienia score)
        llm_eligible=False,
    )
