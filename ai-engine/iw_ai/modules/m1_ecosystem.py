"""Moduł 1 – Monitoring ekosystemu zewnętrznego (finfluencerzy i podmioty trzecie).

Wykrywa reklamy firm inwestycyjnych z rejestru KNF (w tym polskojęzyczne reklamy zagranicznych firm działających
transgranicznie), publikowane przez podmioty trzecie lub osoby prywatne – poza własnymi kanałami firmy.
Wynik: dane firmy, dane podmiotu reklamującego, treść reklamy, URL; okresową aktualizację zapewnia backend
(ponowne odwiedziny znanych reklam – first_seen / last_seen / usunięta).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from ..context import Ctx
from ..embeddings import get_embedder
from ..registry import domain_matches, host_of
from ..schemas import Reason, UnifiedFinding
from ..scoring import compile_patterns, excerpt_around, find_hits, semantic_feature, sigmoid
from .m2_compliance import LABEL_RX

PROMO = compile_patterns([
    ("link afiliacyjny / w bio", r"link\w* (w bio|w opisie|ponizej|pod filmem|w komentarzu)|z mojego linku|moj link|przez (moj|ten) link", 1.2),
    ("kod polecający / promocyjny", r"kod\w* (polecajac|promocyjn|rabatow|partnersk)\w*|z kodem [a-z0-9]{3,}|kod [a-z0-9]{4,} (daje|na)", 1.4),
    ("oznaczenie współpracy", r"#(ad|reklama|wspolpraca|sponsored|partner)\b|wspolpraca (reklamowa|platna|z marka)|material sponsorowany|post sponsorowany|partnerem (materialu|odcinka|filmu)", 1.1),
    ("wezwanie do otwarcia rachunku", r"(zaloz|otworz|otworzcie|zarejestruj)\w* (sie|konto|rachunek)|zalozysz konto|dolacz do (mnie|nas) w", 0.9),
    ("bonus / prezent", r"bonus\w*|darmow\w* (akcj|prowizj|transakcj)|zgarnij|w prezencie|cashback|0 ?zl prowizji|bez prowizji", 0.8),
    ("rekomendacja osobista", r"\bpolecam\b|uzywam od|handluje (tam|u nich)|moj ulubiony broker|najlepszy broker", 0.7),
    ("obietnica zysku", r"zarobil\w* \d|zarob\w*|zysk\w* (nawet|do) \d+|pasywny dochod|wolnosc finansow", 0.5),
])
NEWS = compile_patterns([
    ("język prasowy", r"\b(poinformowal\w*|komunikat\w*|wedlug danych|jak podaje|redakcja|agencja|pap|raport\w* kwartaln)\b", 0.9),
    ("krytyka / skarga", r"\b(skarg\w*|reklamacj\w*|oszuk\w*|uwazajcie|ostrzegam|nie polecam|problem z wyplata)\b", 1.0),
    ("pytanie / dyskusja", r"czy ktos (ma|korzysta|wie)|jakie macie doswiadczenia|co sadzicie", 0.8),
    ("ranking redakcyjny bez współpracy", r"metodologi\w* rankingu|niezalezn\w* (ranking|porownani)", 0.6),
])
AFF_PARAMS = {"ref", "aff", "affiliate", "partner", "promo", "utm_source", "utm_medium", "pid", "refcode", "invite", "code"}
PROTOTYPES = ["zarejestruj się z moim linkiem polecającym i odbierz bonus na start w biurze maklerskim",
              "współpraca reklamowa materiał sponsorowany otwórz rachunek kod rabatowy link w bio",
              "polecam tego brokera, handluję tam od roku, kod promocyjny daje darmowe prowizje"]


def affiliate_links(links: list[str], domains: list[str]) -> list[str]:
    out = []
    for link in links:
        h = host_of(link)
        if h and domains and domain_matches(h, domains):
            try:
                u = urlparse(link)
            except ValueError:
                continue
            q = {k.lower() for k in parse_qs(u.query)}
            if q & AFF_PARAMS or re.search(r"/(ref|r|invite|partner|go|aff)/", u.path, re.I):
                out.append(link)
    return out


def analyze(ctx: Ctx) -> UnifiedFinding | None:
    if not ctx.is_polish:
        return None
    cands = [m for m in ctx.matches if not (ctx.owner and ctx.owner.id == m.entity.id)
             and (m.entity.is_investment_firm or m.entity.category == "ostrzezenie_knf")]
    if not cands:
        return None
    ranked = sorted(((len(affiliate_links(ctx.doc.links, m.entity.domains)), m.by == "domain_link", m) for m in cands),
                    key=lambda t: (t[0], t[1]), reverse=True)
    match = ranked[0][2]
    ent = match.entity
    aff = affiliate_links(ctx.doc.links, ent.domains)
    promo = find_hits(PROMO, ctx.folded, "promo", display=ctx.display)
    news = find_hits(NEWS, ctx.folded, "news", display=ctx.display)
    labeled = bool(LABEL_RX.search(ctx.folded)) or any(h.label == "oznaczenie współpracy" for h in promo)
    sim = get_embedder().similarity_to(ctx.pre.embedding, ctx.pre.embedding_model, PROTOTYPES)
    links_to_firm = any(domain_matches(host_of(l), ent.domains) for l in ctx.doc.links if ent.domains)

    contrib = {
        "promocja": min(sum(h.weight for h in promo), 4.0),
        "link_afiliacyjny": 1.8 if aff else 0.0,
        "link_do_firmy": 0.4 if links_to_firm else 0.0,
        "kanal_social": 0.5 if ctx.is_social else 0.0,
        "semantyka": semantic_feature(sim, ctx.pre.embedding_model),
        "prasa_krytyka": -min(sum(h.weight for h in news), 2.5),
    }
    rule_score = sigmoid(-2.0 + sum(contrib.values()))
    is_ad = rule_score >= 0.5

    if ent.category == "ostrzezenie_knf":
        category = "promocja_podmiotu_z_listy_ostrzezen_KNF"
    elif ent.category in {"zagraniczna_firma_transgraniczna", "oddzial_zagranicznej_firmy"} and ent.country != "PL":
        category = "reklama_zagranicznej_firmy_inwestycyjnej"
    elif ctx.is_social:
        category = "reklama_finfluencer"
    else:
        category = "reklama_podmiot_trzeci"

    reasons = list(promo)
    if aff:
        reasons.append(Reason(rule="promo:affiliate_url", label="link afiliacyjny do firmy", evidence=aff[0], weight=1.8))
    if is_ad and not labeled:
        reasons.append(Reason(rule="promo:unlabeled", label="reklama nieoznaczona jako współpraca/reklama", weight=0.0,
                              evidence="brak #reklama / „materiał sponsorowany” / „współpraca”"))
    reasons += [Reason(rule=h.rule, label=h.label, evidence=h.evidence, weight=-h.weight) for h in news]

    return UnifiedFinding(
        module=1, module_name="Ekosystem zewnętrzny (finfluencerzy i podmioty trzecie)",
        category=category, score=round(rule_score, 4), rule_score=round(rule_score, 4),
        firm={"id": ent.id, "name": ent.name, "category": ent.category, "country": ent.country,
              "register_id": ent.register_id, "authorized": ent.authorized, "matched_by": match.by},
        advertiser={"name": ctx.doc.author or ctx.doc.site_name or ctx.doc.domain,
                    "url": ctx.doc.author_url or f"https://{ctx.doc.domain}", "platform": ctx.doc.source_type,
                    "is_labeled_ad": labeled, "reach": ctx.doc.metrics},
        excerpt=excerpt_around(ctx.text, promo[0].evidence if promo else match.evidence),
        reasons=reasons,
        details={"affiliate_links": aff[:5], "matched_by": match.by, "labeled_ad": labeled,
                 "contributions": {k: round(v, 3) for k, v in contrib.items()}, "semantic_similarity": round(sim, 3),
                 "other_firms": [m.entity.name for *_, m in ranked[1:]]},
    )
