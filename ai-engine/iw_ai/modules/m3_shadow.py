"""Moduł 3 – Identyfikacja usług nieautoryzowanych (Shadow Advisory).

Definicja (załącznik do Tematu 3, art. 76 u.o.i.f.): doradztwo inwestycyjne to przekazywanie klientowi
rekomendacji przygotowanej w oparciu o jego potrzeby i sytuację, dotyczącej nabycia, zbycia lub powstrzymania się
od transakcji (trzymania) instrumentów finansowych (art. 2 i 3 u.o.i.f.).
Model sprawdza więc trzy elementy definicji jednocześnie:
  A – personalizacja (potrzeby / sytuacja / profil klienta),
  B – rekomendacja transakcji (kup / sprzedaj / trzymaj, dobór instrumentów, sygnały),
  C – przedmiot: instrumenty finansowe z zamkniętego katalogu art. 2 (kryptoaktywa, złoto fizyczne,
      nieruchomości – poza katalogiem),
oraz kontekst: brak w rejestrze firm inwestycyjnych, Lista ostrzeżeń KNF, odpłatność, branding usługi.
"""
from __future__ import annotations

import re

from ..context import Ctx
from ..embeddings import get_embedder
from ..entity_extract import extract_entity
from ..schemas import Reason, UnifiedFinding
from ..scoring import compile_patterns, excerpt_around, find_hits, semantic_feature, sigmoid

PERSONAL = compile_patterns([  # A
    ("dopasowanie do sytuacji klienta", r"(dopasowan|dostosowan|skrojon)\w* do (twoj|panstwa|pana|pani|indywidualn)\w* (sytuacj|potrzeb|cel|profil|oczekiwan)\w*|w oparciu o (twoje|panstwa) (potrzeby|cele|sytuacj)\w*", 1.4),
    ("indywidualne / spersonalizowane", r"(indywidualn|spersonalizowan|osobist)\w* (rekomendacj|strategi|porad|plan\w* inwestycyjn|dobor|portfel|konsultacj)\w*", 1.4),
    ("analiza sytuacji / profil ryzyka", r"(analiz|ocen)\w* (twojej|panstwa|pana|pani) (sytuacji|portfela|profilu)|profil\w* ryzyka|ankiet\w* inwestycyjn", 1.0),
])
RECOMMEND = compile_patterns([  # B
    ("rekomendacje kupna / sprzedaży", r"rekomendacj\w* (inwestycyjn|zakupu|sprzedazy|kupna|nabycia|zbycia|dotyczac)\w*|zalecamy (zakup|sprzedaz|kupno)|rekomendujemy (zakup|sprzedaz|kupno|trzymanie)", 1.6),
    ("co i kiedy kupić / sprzedać", r"(powiemy|podpowiemy|doradzimy|wskazemy|dowiesz sie),? (ci |panstwu |tobie )?(co|ktore|kiedy|jakie|jak) (kupic|sprzedac|inwestowac|trzymac)|(co|ktore akcje) i kiedy (kupic|sprzedac)", 1.5),
    ("dobór instrumentów", r"dobier\w* (dla (ciebie|pana|pani|panstwa) )?(instrument|akcj|obligacj|fundusz|etf|spol|aktyw)\w*|dobor\w* (instrument|akcj|spolek|funduszy|etf|aktyw)\w*|wskazemy,? (ktore|jakie) (akcje|fundusze|etf|instrumenty)", 1.4),
    ("sygnały transakcyjne / copy trading", r"sygnal\w* (transakcyjn|kupna|sprzedazy|inwestycyjn)\w*|kopiuj\w* (moje )?transakcj\w*|copy ?trading|alerty (kupna|sprzedazy)", 1.5),
    ("zarządzanie / przebudowa portfela", r"zarzadza\w* (twoim |panstwa |pana |pani )?(portfel|majatk|aktyw|kapital|oszczednosc)\w*|(przebudow|optymalizacj|rebalans|alokacj)\w* (twojego |panstwa )?(portfel|aktyw|kapital)\w*", 1.3),
    # art. 76 u.o.i.f.: także rekomendacja powstrzymania się od transakcji (trzymaj / nie sprzedawaj / wstrzymaj zakup)
    ("rekomendacje trzymania / powstrzymania się", r"(rekomendujemy|zalecamy|radzimy|doradzamy|sugerujemy) (dalsze )?(trzymanie|wstrzymanie sie|powstrzymanie sie)|(wstrzymaj|powstrzymaj)\w* sie (z|od) (zakup|sprzedaz|kupn|transakcj|inwestowan)\w*|(nie sprzedawaj|nie kupuj)\w* (teraz |jeszcze |tych |tej )?(akcj|obligacj|jednost|etf|spolk)\w*", 1.4),
])
INSTRUMENTS = compile_patterns([  # C – art. 2 i 3 u.o.i.f.
    ("papiery wartościowe (akcje, obligacje, warranty, certyfikaty)", r"\b(akcj\w*|obligacj\w*|warrant\w*|praw\w* poboru|certyfikat\w* inwestycyjn\w*|list\w* zastawn\w*|kwit\w* depozytow\w*|spolk\w* gieldow\w*)\b", 1.0),
    ("tytuły uczestnictwa (fundusze, ETF)", r"\b(etf\w*|jednost\w* uczestnictwa|fundusz\w* inwestycyjn\w*|fundusz\w*)\b", 0.9),
    ("instrumenty pochodne / CFD", r"\b(cfd|kontrakt\w* (terminow|na roznic)\w*|opcj\w*|swap\w*|instrument\w* pochodn\w*|futures)\b", 1.0),
    ("instrumenty finansowe (ogólnie)", r"instrument\w* finansow\w*|papier\w* wartosciow\w*", 0.8),
    ("instrumenty rynku pieniężnego", r"instrument\w* rynku pienieznego|bon\w* skarbow\w*|bon\w* pieniezn\w*|papier\w* komercyjn\w*|certyfikat\w* depozytow\w*", 0.9),
    ("uprawnienia do emisji", r"uprawnie\w* do emisji|\beua\b|emisj\w* co2", 0.9),
    ("prawa pochodne, prawa do akcji", r"praw\w* (pochodn|do akcji)\w*|\bpda\b|bankow\w* (papier|praw)\w* (wartosciow|pochodn)\w*|credit default swap|\bcds\b", 0.8),
])
NON_INSTRUMENTS = re.compile(r"kryptowalut\w*|kryptoaktyw\w*|bitcoin\w*|\bbtc\b|ethereum|altcoin\w*|token\w*|nft\b|"
                             r"zloto fizyczn\w*|sztabk\w*|nieruchomos\w*|monet\w* kolekcjon", re.I)
SERVICE = compile_patterns([
    ("branding usługi doradczej", r"wealth management|family office|private (wealth|banking)|investment consulting|asset management|doradztw\w* inwestycyjn\w*|doradc\w* (inwestycyjn|finansow)\w*", 0.9),
    ("odpłatność", r"\b(cennik|abonament\w*|success fee|oplat\w* (za usluge|miesieczn|roczn)|wynagrodzeni\w*|\d+ ?zl ?(/|za|miesiecznie|netto|brutto|mies))", 0.7),
    ("pozyskiwanie klientów", r"umow\w* (sie|spotkanie|konsultacj|rozmow)|bezplatn\w* konsultacj|skontaktuj|zapisz sie|formularz kontaktowy|grupa vip|napisz do nas", 0.5),
])
NEGATIVE = compile_patterns([
    ("zastrzeżenie: brak rekomendacji", r"nie stanowi\w* (rekomendacji|porady|doradztwa)|nie (swiadczymy|swiadczy) (uslug\w* )?doradztwa inwestycyjnego|nie jest (to )?rekomendacj", 1.3),
    ("edukacja ogólna", r"(material|cel\w*|tresc\w*|kurs\w*) (wylacznie |ma charakter )?edukacyjn\w*|w celach edukacyjnych|kurs\w* (dla poczatkujacych|podstaw)", 0.9),
    ("inna działalność (podatki, księgowość, ubezpieczenia)", r"doradztw\w* podatkow\w*|biuro rachunkow\w*|ksiegowos\w*|ubezpieczeni\w* (na zycie|majatkow|komunikacyjn)|posrednik\w* ubezpieczeniow|kredyt\w* hipoteczn", 1.0),
    ("współpraca z licencjonowaną firmą / agent", r"we wspolpracy z (licencjonowan|autoryzowan)\w*|agent\w* firmy inwestycyjnej|nadzorowan\w* przez knf,? (ktory|ktora) (odpowiada|swiadczy)|w imieniu domu maklerskiego", 1.1),
    ("opinia własna / ogólna", r"(moim zdaniem|moja opinia|kupuje (dla siebie|do swojego portfela)|nie znam twojej sytuacji)", 0.7),
])
PROTOTYPES = ["indywidualne rekomendacje inwestycyjne dobór akcji i obligacji do Twojej sytuacji i profilu ryzyka",
              "zarządzamy majątkiem klientów family office wealth management doradztwo inwestycyjne",
              "powiemy Ci które akcje kupić i kiedy sprzedać sygnały transakcyjne grupa VIP abonament"]


def _sum(hits, cap):
    return min(sum(h.weight for h in hits), cap)


def analyze(ctx: Ctx) -> UnifiedFinding | None:
    if ctx.owner is not None and (ctx.owner.is_investment_firm or ctx.owner.is_registered_agent):
        return None                                   # autoryzowana firma inwestycyjna albo jej agent (rejestr KNF) – poza zakresem
    A = find_hits(PERSONAL, ctx.folded, "A", display=ctx.display)
    B = find_hits(RECOMMEND, ctx.folded, "B", display=ctx.display)
    S = find_hits(SERVICE, ctx.folded, "svc", display=ctx.display)
    if not (A or B or any(h.label.startswith("branding") for h in S)):
        return None
    C = find_hits(INSTRUMENTS, ctx.folded, "C", display=ctx.display)
    N = find_hits(NEGATIVE, ctx.folded, "neg", display=ctx.display)
    non_instr = NON_INSTRUMENTS.findall(ctx.folded)
    warned_owner = ctx.owner is not None and ctx.owner.category == "ostrzezenie_knf"
    warned_mention = [m for m in ctx.matches if m.entity.category == "ostrzezenie_knf"]
    firm_mentions = [m for m in ctx.matches if m.entity.is_investment_firm]
    sim = get_embedder().similarity_to(ctx.pre.embedding, ctx.pre.embedding_model, PROTOTYPES)

    definition = {"A_personalizacja": bool(A), "B_rekomendacja": bool(B), "C_instrument_finansowy": bool(C)}
    crypto_only = bool(non_instr) and not C
    contrib = {
        "A_personalizacja": _sum(A, 1.8),
        "B_rekomendacja": _sum(B, 2.2),
        "C_instrumenty_art2": 0.8 if C else (-2.6 if crypto_only else -0.6),
        "A_B_C_lacznie": 1.2 if all(definition.values()) else 0.0,
        "usluga_komercyjna": _sum(S, 1.4),
        "lista_ostrzezen_KNF": 2.5 if warned_owner else (0.9 if warned_mention else 0.0),
        "powiazanie_z_firma_inwestycyjna": -0.6 if firm_mentions else 0.0,
        "semantyka": semantic_feature(sim, ctx.pre.embedding_model, 3.0),
        "zastrzezenia_kontekst": -_sum(N, 3.0),
    }
    rule_score = sigmoid(-3.2 + sum(contrib.values()))

    labels = {h.label for h in B}
    if warned_owner or warned_mention:
        category = "podmiot_z_listy_ostrzezen_KNF"
    elif crypto_only:
        category = "poza_art_2_uoif_kryptoaktywa"
    elif "sygnały transakcyjne / copy trading" in labels:
        category = "sygnaly_transakcyjne_bez_zezwolenia"
    elif "zarządzanie / przebudowa portfela" in labels:
        category = "zarzadzanie_portfelem_bez_zezwolenia"
    else:
        category = "doradztwo_inwestycyjne_bez_zezwolenia"

    # na platformie społecznościowej podmiotem jest autor konta, nie serwis (site_name = „facebook”)
    name = (ctx.owner.name if ctx.owner else None) or (
        ctx.doc.author if ctx.is_social else (ctx.doc.site_name or ctx.doc.author)) or ctx.doc.domain
    entity = extract_entity(ctx.text, name)
    reasons = list(A) + list(B) + list(C) + list(S)
    if warned_owner or warned_mention:
        reasons.insert(0, Reason(rule="registry:warning_list", label="podmiot na Liście ostrzeżeń publicznych KNF",
                                 evidence=(ctx.owner.name if warned_owner else warned_mention[0].entity.name), weight=2.5))
    if crypto_only:
        reasons.append(Reason(rule="C:poza_katalogiem", label="przedmiot usługi spoza katalogu art. 2 u.o.i.f. (kryptoaktywa itp.)",
                              evidence=", ".join(sorted(set(non_instr))[:4]), weight=-2.6))
    reasons += [Reason(rule=h.rule, label=h.label, evidence=h.evidence, weight=-h.weight) for h in N]
    strongest = max(B or A or S, key=lambda h: h.weight)
    return UnifiedFinding(
        module=3, module_name="Usługi nieautoryzowane (shadow advisory)",
        category=category, score=round(rule_score, 4), rule_score=round(rule_score, 4),
        firm={"id": ctx.owner.id if ctx.owner else None, "name": entity.name or name,
              "category": ctx.owner.category if ctx.owner else "brak_w_rejestrze",
              "authorized": False, "matched_by": ctx.owner_by},
        advertiser={"name": ctx.doc.author or name, "url": ctx.doc.author_url or f"https://{ctx.doc.domain}",
                    "platform": ctx.doc.source_type, "reach": ctx.doc.metrics},
        entity=entity,
        excerpt=excerpt_around(ctx.text, strongest.evidence),
        reasons=reasons,
        details={"definition_art76": definition, "in_investment_firm_register": False,
                 "on_warning_list": bool(warned_owner or warned_mention),
                 "related_investment_firms": [m.entity.name for m in firm_mentions],
                 "contributions": {k: round(v, 3) for k, v in contrib.items()}, "semantic_similarity": round(sim, 3)},
    )
