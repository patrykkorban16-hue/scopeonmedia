"""Generator zbioru demonstracyjno-walidacyjnego (FIKCYJNE podmioty, domeny *.test).

Tworzy mini-internet serwowany przez API pod /demo/sites/ oraz odpowiedzi mock API platform (/demo/api/<platforma>).
Każdy materiał ma etykietę `iw-ground-truth` {"<moduł>": true/false} – zbiór walidacyjny Panelu Kalibracji.
Zbiór celowo zawiera przypadki graniczne (np. nieoznaczona rekomendacja brokera, drobne uchybienia), aby zmiana
progu realnie przesuwała równowagę FP/FN.

    python -m iw_backend.demo.make_demo
"""
from __future__ import annotations

import html as h
import json
from pathlib import Path

ROOT = Path(__file__).parent
SITES, SOCIAL = ROOT / "sites", ROOT / "social"

BASE_CSS = """body{font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#1f2933;background:#fff;max-width:900px;margin:0 auto;padding:16px}
h1{font-size:34px}.hero{font-size:24px;font-weight:bold}.box{border:2px solid #b42318;padding:12px;margin:12px 0}
.legal{font-size:9px;color:#c4c4c4}.fine{font-size:10px;color:#9aa0a6}footer{margin-top:40px;border-top:1px solid #ddd;padding-top:8px}
.muted{color:#b0b0b0}.ad-label{font-size:12px;color:#555}"""

VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'

# (ścieżka, kanoniczny URL, tytuł, data, etykiety, site_name, autor, body, dodatkowy CSS, viewport)
P = []


def page(path, canonical, title, date, gt, site, author, body, css="", viewport=True, ld=None):
    P.append((path, canonical, title, date, gt, site, author, body, css, viewport, ld))


# =============================================================== MODUŁ 2 – materiały firm inwestycyjnych
page("vistula-dm/promocja-start.html", "https://vistula-dm.test/promocja-start", "Vistula Trade – zarabiaj bez ryzyka",
     "2026-10-02", {"2": True}, "Vistula Trade", None, """
<h1>Zarabiaj nawet 25% rocznie z Vistula Trade!</h1>
<p class="hero">Gwarantowany zysk na portfelu obligacji – inwestycja bez ryzyka.</p>
<p>Otwórz rachunek i pomnóż oszczędności. Tylko dziś 0 zł prowizji na start!</p>
<p>Nasi klienci zarobili +31% w 2025 roku. Dołącz do tysięcy zadowolonych inwestorów.</p>
<footer><p class="legal">* Inwestowanie wiąże się z ryzykiem.</p></footer>""")

page("vistula-dm/rachunek-maklerski.html", "https://vistula-dm.test/rachunek-maklerski", "Rachunek maklerski – Vistula DM",
     "2026-10-05", {"2": False}, "Vistula Dom Maklerski", None, """
<p class="ad-label">Materiał marketingowy</p>
<h1>Rachunek maklerski w Vistula DM</h1>
<p>Akcje i ETF z GPW oraz rynków zagranicznych. Prowizja od 0,29% wartości zlecenia.</p>
<div class="box"><strong>Ostrzeżenie o ryzyku:</strong> inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty
części lub całości zainwestowanych środków. Wartość akcji może spaść.</div>
<p>Vistula Dom Maklerski S.A. działa na podstawie zezwolenia Komisji Nadzoru Finansowego.</p>""")

page("vistula-dm/fundusze-w-ofercie.html", "https://vistula-dm.test/fundusze", "Fundusze w ofercie Vistula DM",
     "2026-10-09", {"2": True}, "Vistula Dom Maklerski", None, """
<p class="ad-label">Materiał marketingowy Vistula Dom Maklerski S.A.</p>
<h1>Fundusze akcji globalnych w ofercie</h1>
<p>Stopy zwrotu funduszu Global Equity: 2021: +8,2%, 2022: -12,4%, 2023: +15,1%, 2024: +9,7%, 2025: +11,3%.
Źródło: obliczenia własne na podstawie wycen jednostek, wyniki po uwzględnieniu opłat. Fundusz inwestuje w USD –
zmiany kursów walut wpływają na wynik.</p>
<p>Past performance is not a reliable indicator of future results. Capital at risk – you may lose money.</p>""")

page("vistula-dm/ike.html", "https://vistula-dm.test/ike", "IKE w Vistula DM – bez podatku Belki",
     "2026-10-12", {"2": True}, "Vistula Dom Maklerski", None, """
<p class="ad-label">Reklama</p>
<h1>IKE maklerskie – oszczędzaj bez podatku Belki</h1>
<p>Vistula Dom Maklerski S.A. zaprasza do otwarcia IKE. Zyski z IKE są zwolnione z podatku od zysków kapitałowych.</p>
<p>Inwestowanie wiąże się z ryzykiem utraty części zainwestowanych środków.</p>""")

page("vistula-dm/porownanie.html", "https://vistula-dm.test/vs-lokata", "Vistula Trade vs lokata",
     "2026-10-27", {"2": True}, "Vistula Trade", None, """
<p class="ad-label">Reklama Vistula Dom Maklerski S.A.</p>
<h1>Nawet 3 razy więcej niż lokata</h1>
<p>Obligacje korporacyjne w Vistula Trade dają wyższy zwrot niż lokata bankowa. Najniższe prowizje na rynku.</p>
<p>Inwestowanie wiąże się z ryzykiem utraty części kapitału; wartość obligacji może spaść.</p>""")

page("nordfx/cfd-zloto.html", "https://nordfx-markets.test/pl/cfd-zloto", "NordFX – złoto z dźwignią 1:30",
     "2026-10-08", {"2": True}, "NordFX Markets", None, """
<h1>Złoto, ropa, indeksy – kontrakty CFD w NordFX</h1>
<p class="hero">Zyski nawet do 300% w miesiąc dzięki dźwigni finansowej 1:30!</p>
<p>Ponad 2000 instrumentów CFD, spready od 0,1 pipsa. Zarabiaj na wzrostach i spadkach. Bonus 500 zł na start.</p>
<p>Nasi najlepsi traderzy zarobili +180% w ostatnich 12 miesiącach.</p>
<footer><small class="fine">CFD są instrumentami złożonymi. Handel wiąże się z ryzykiem. NordFX Markets Ltd, Limassol.</small></footer>""")

page("nordfx/cfd.html", "https://nordfx-markets.test/pl/cfd", "Kontrakty CFD – NordFX Markets Ltd",
     "2026-10-11", {"2": False}, "NordFX Markets", None, """
<div class="box"><strong>Kontrakty CFD są złożonymi instrumentami i wiążą się z wysokim ryzykiem szybkiej utraty środków
z powodu dźwigni finansowej. 74% rachunków inwestorów detalicznych odnotowuje straty w wyniku handlu kontraktami CFD
u tego dostawcy.</strong> Zastanów się, czy rozumiesz, jak działają kontrakty CFD, i czy możesz pozwolić sobie na wysokie
ryzyko utraty pieniędzy.</div>
<p class="ad-label">Materiał marketingowy NordFX Markets Ltd</p>
<h1>Kontrakty CFD w NordFX</h1>
<p>Kontrakty CFD na indeksy, surowce i waluty. Dźwignia dla klientów detalicznych maksymalnie 1:30.</p>""")

page("nordfx/kalkulator.html", "https://nordfx-markets.test/pl/kalkulator", "Kalkulator zysku – NordFX Markets Ltd",
     "2026-11-03", {"2": False}, "NordFX Markets", None, """
<p class="ad-label">Materiał marketingowy NordFX Markets Ltd</p>
<h1>Symulacja wyniku na indeksie DAX</h1>
<p>Przykład: przy wzroście indeksu o 2% pozycja o wartości 10 000 zł może przynieść 200 zł zysku, a przy spadku o 2% –
200 zł straty. Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.</p>
<div class="box">Kontrakty CFD wiążą się z wysokim ryzykiem szybkiej utraty środków. 74% rachunków inwestorów
detalicznych odnotowuje straty w wyniku handlu kontraktami CFD u tego dostawcy.</div>""")

page("bank-nadwislanski/obligacje.html", "https://bank-nadwislanski.test/inwestycje/obligacje",
     "Obligacje – Biuro Maklerskie Banku Nadwiślańskiego", "2026-10-14", {"2": True}, "Bank Nadwiślański", None, """
<h1>Pewny zysk 9% rocznie</h1>
<p class="hero">Obligacje zatwierdzone przez KNF – bezpieczna inwestycja dla Twoich oszczędności.</p>
<p>Bank Nadwiślański S.A. – Biuro Maklerskie zaprasza na zapisy. Ostatnie miejsca!</p>""")

page("bank-nadwislanski/konto-maklerskie.html", "https://bank-nadwislanski.test/inwestycje/konto",
     "Konto maklerskie – Bank Nadwiślański", "2026-10-17", {"2": True}, "Bank Nadwiślański", None, """
<h1>Konto maklerskie w Banku Nadwiślańskim</h1>
<p>Inwestuj na GPW z aplikacji mobilnej. Prowizja 0,25%, minimum 3 zł. Bank Nadwiślański S.A. prowadzi działalność
maklerską w wyodrębnionej jednostce – Biurze Maklerskim.</p>
<p style="font-size:14px">Inwestowanie wiąże się z ryzykiem utraty części lub całości zainwestowanych środków.</p>""")

page("bank-nadwislanski/kontrast.html", "https://bank-nadwislanski.test/inwestycje/etf",
     "ETF – Bank Nadwiślański S.A.", "2026-10-29", {"2": True}, "Bank Nadwiślański", None, """
<p class="ad-label">Reklama Bank Nadwiślański S.A.</p>
<h1>Zarabiaj z ETF-ami na cały świat</h1>
<p>Fundusze ETF pozwalają zarabiać na wzrostach globalnych rynków przy niskich kosztach.</p>
<p class="muted">Inwestowanie w ETF wiąże się z ryzykiem utraty części zainwestowanych środków.</p>""")

page("kopernik/obligacje.html", "https://kopernik-securities.test/oferta/obligacje", "Obligacje 11% – Kopernik Securities",
     "2026-10-20", {"2": True}, "Kopernik Securities", None, """
<h1>Obligacje z oprocentowaniem 11% rocznie</h1>
<p class="hero">Wysoki zwrot co kwartał. Stabilny dochód dla Twoich oszczędności.</p>
<p>Kopernik Securities S.A. – oferujący w publicznej ofercie obligacji serii K3. Zapisy tylko do piątku!</p>""")

page("kopernik/ike.html", "https://kopernik-securities.test/ike", "IKE maklerskie – Kopernik Securities",
     "2026-10-23", {"2": False}, "Kopernik Securities", None, """
<p class="ad-label">Materiał marketingowy</p>
<h1>IKE maklerskie w Kopernik Securities S.A.</h1>
<p>Oszczędzaj na emeryturę z ulgą podatkową. Samodzielnie wybierasz akcje, obligacje i ETF.</p>
<p><strong>Inwestowanie wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału.</strong> Wartość instrumentów
finansowych może spaść.</p>
<p>Zwolnienie z podatku od zysków kapitałowych dotyczy wypłaty po spełnieniu warunków ustawowych. Sposób opodatkowania
zależy od indywidualnej sytuacji klienta i może ulec zmianie w przyszłości.</p>""")

page("kopernik/bezpieczenstwo.html", "https://kopernik-securities.test/dlaczego-my", "Dlaczego Kopernik Securities",
     "2026-11-04", {"2": True}, "Kopernik Securities", None, """
<p class="ad-label">Materiał marketingowy Kopernik Securities S.A.</p>
<h1>Twoje pieniądze są u nas bezpieczne</h1>
<p>Inwestycje w naszej ofercie są w pełni bezpieczne – spełniamy rygorystyczne wymogi nadzorcze KNF.</p>
<p>Inwestowanie wiąże się z ryzykiem utraty części kapitału.</p>""")

page("alpine/fundusz-akcji.html", "https://alpine-capital.test/pl/akcje-europa", "Akcje europejskie – Alpine Capital",
     "2026-10-16", {"2": True}, "Alpine Capital", None, """
<p class="ad-label">Materiał marketingowy Alpine Capital AG Oddział w Polsce</p>
<h1>Zarabiaj na liderach europejskiej giełdy</h1>
<p>Portfel modelowy akcji europejskich zyskał 18% w 2025 roku. Inwestuj od 1000 zł.</p>
<details><summary>Informacje prawne</summary><p>Inwestowanie wiąże się z ryzykiem utraty środków. Historyczne wyniki nie
gwarantują osiągnięcia podobnych wyników w przyszłości.</p></details>""")

page("alpine/mobile.html", "https://alpine-capital.test/pl/obligacje", "Obligacje – Alpine Capital",
     "2026-11-06", {"2": True}, "Alpine Capital", None, """
<p class="ad-label">Materiał marketingowy Alpine Capital AG Oddział w Polsce</p>
<h1>Obligacje z kuponem 7%</h1>
<p>Stały kupon wypłacany co pół roku. Minimalna inwestycja 5000 zł.</p>
<p class="risk">Inwestowanie w obligacje wiąże się z ryzykiem utraty części zainwestowanych środków, w tym ryzykiem niewypłacalności emitenta.</p>""",
     css="@media (max-width: 600px){ .risk{display:none} }")

# =============================================================== MODUŁ 1 – podmioty trzecie, finfluencerzy
page("blogi/finansowy-kuba.html", "https://finansowykuba.test/2026/10/najlepszy-broker", "Jaki broker na start? – Finansowy Kuba",
     "2026-10-03", {"1": True}, "Finansowy Kuba", "Jakub „Finansowy Kuba” W.", """
<h1>Jaki broker na start? Polecam Vistula Trade</h1>
<p>Handluję u nich od dwóch lat i to mój ulubiony broker. Zero prowizji przez pierwsze 3 miesiące!</p>
<p>Załóż konto z mojego linku i zgarnij bonus 200 zł: <a href="https://vistula-dm.test/otworz-rachunek?ref=FINKUBA">vistula-dm.test</a>.
Kod polecający: FINKUBA.</p><p>#reklama #współpraca – wpis powstał we współpracy z marką.</p>""")

page("blogi/forex-mistrz.html", "https://forexmistrz.test/nordfx-recenzja", "NordFX – recenzja i bonus | ForexMistrz",
     "2026-10-09", {"1": True}, "ForexMistrz", "Michał Trader", """
<h1>NordFX: dźwignia, bonus i moje wyniki</h1>
<p>Zarobiłem na złocie 40% w miesiąc! Polecam NordFX – najlepszy broker CFD dla Polaków.</p>
<p>Zarejestruj się przez <a href="https://nordfx-markets.test/pl/register?aff=8841&utm_source=forexmistrz">mój link partnerski</a>
i odbierz bonus 500 zł na pierwszy depozyt.</p>""")

page("news/rynek-maklerski.html", "https://biznes-wiadomosci.test/rynek/domy-maklerskie-2026",
     "Domy maklerskie raportują rekordowe wolumeny", "2026-10-12", {"1": False}, "Biznes Wiadomości", "Redakcja", """
<h1>Domy maklerskie raportują rekordowe wolumeny</h1>
<p>Jak podaje Izba Domów Maklerskich, w trzecim kwartale liczba rachunków wzrosła o 4%. Vistula Dom Maklerski S.A.
poinformował w komunikacie o 12-procentowym wzroście liczby klientów, a Bank Nadwiślański odnotował rekord obrotów.</p>
<p>Według danych GPW obroty akcjami wzrosły r/r o 18%.</p>""")

page("forum/kopernik-wyplata.html", "https://forum-inwestorow.test/t/kopernik-wyplata", "Kopernik Securities – problem z wypłatą?",
     "2026-10-15", {"1": False}, "Forum Inwestorów", "user_bartek88", """
<h1>Kopernik Securities – problem z wypłatą?</h1>
<p>Czy ktoś ma doświadczenie z Kopernik Securities? Od tygodnia czekam na przelew, reklamacja bez odpowiedzi.</p>
<p>Uważajcie, nie polecam na razie, dam znać jak się wyjaśni.</p>""")

page("blogi/ranking-oszczedzania.html", "https://oszczedzaj-madrze.test/ranking-kont", "Ranking kont maklerskich 2026",
     "2026-10-21", {"1": True}, "Oszczędzaj Mądrze", "Anna K.", """
<h1>Ranking kont maklerskich: Bank Nadwiślański zwycięzcą!</h1>
<p>Materiał sponsorowany. Konto maklerskie Banku Nadwiślańskiego to moim zdaniem najlepszy wybór dla początkujących.</p>
<p>Otwórz konto przez <a href="https://bank-nadwislanski.test/konto?partner=oszczedzaj">ten link</a> – z kodem MADRZE bez prowizji przez 6 miesięcy.</p>""")

page("blogi/goldstar-okazja.html", "https://pasywny-dochod.test/goldstar", "Pasywny dochód z GoldStar Capital",
     "2026-10-25", {"1": True}, "Pasywny Dochód", "Ola Inwestuje", """
<h1>Mój pasywny dochód z GoldStar Capital</h1>
<p>Polecam GoldStar Capital – od pół roku zarabiam 8% miesięcznie. Zarejestruj się z mojego linku
<a href="https://goldstar-capital.test/join?ref=OLA">goldstar-capital.test</a> i odbierz bonus. #współpraca</p>""")

page("blogi/porownanie-prowizji.html", "https://niezalezny-inwestor.test/porownanie-prowizji-2026",
     "Porównanie prowizji maklerskich 2026", "2026-11-01", {"1": False}, "Niezależny Inwestor", "Redakcja NI", """
<h1>Porównanie prowizji: Vistula DM, Kopernik Securities, Bank Nadwiślański</h1>
<p>Niezależny ranking redakcyjny. Metodologia rankingu: porównujemy tabele opłat na dzień 1.11.2026 dla zlecenia 5000 zł.</p>
<p>Vistula DM: 0,29%, Kopernik Securities: 0,35%, Bank Nadwiślański: 0,25%. Nie otrzymujemy wynagrodzenia od brokerów.</p>""")

page("blogi/ukryta-reklama.html", "https://zycie-za-milion.test/jak-zaczac-inwestowac", "Jak zacząć inwestować – Życie za milion",
     "2026-11-02", {"1": True}, "Życie za milion", "Marta", """
<h1>Jak zaczęłam inwestować</h1>
<p>Długo się zastanawiałam, gdzie otworzyć konto. Wybrałam NordFX i polecam – aplikacja jest prosta, a na start dostałam bonus.</p>
<p>Wejdźcie na <a href="https://nordfx-markets.test/pl/start">nordfx-markets.test/pl/start</a>, rejestracja zajmuje 5 minut.</p>""")

page("blogi/opinia-klienta.html", "https://domowe-finanse.test/moje-konto-maklerskie", "Moje konto maklerskie po 5 latach",
     "2026-11-05", {"1": False}, "Domowe Finanse", "Piotr", """
<h1>Moje konto maklerskie po 5 latach</h1>
<p>Konto w Banku Nadwiślańskim mam od 2021 roku. Używam od lat głównie do ETF-ów. Aplikacja bywa wolna,
a obsługa klienta różnie. Co sądzicie o alternatywach?</p>""")

# publiczna strona wideo (parser og:* / JSON-LD → source_type wg kanonicznego URL platformy)
page("social/youtube-kopernik.html", "https://www.youtube.com/watch?v=DEMO0000001",
     "Obligacje 11%? Sprawdzam Kopernik Securities", "2026-11-10", {"1": True}, "YouTube", None, """
<h1>Obligacje 11%? Sprawdzam ofertę Kopernik Securities</h1>
<p>Partnerem odcinka jest Kopernik Securities. Z kodem GIELDA50 dostaniesz 50 zł na start – link w opisie:
<a href="https://kopernik-securities.test/oferta/obligacje?ref=gielda">kopernik-securities.test</a></p>""",
     ld={"@context": "https://schema.org", "@type": "VideoObject",
         "author": {"name": "Giełda bez tajemnic (demo)", "url": "https://www.youtube.com/@demo_gielda_bez_tajemnic"},
         "uploadDate": "2026-11-10",
         "interactionStatistic": [{"@type": "InteractionCounter", "interactionType": "https://schema.org/WatchAction",
                                   "userInteractionCount": 64000}]})

# =============================================================== MODUŁ 3 – shadow advisory
page("doradcy/aurum.html", "https://aurum-familyoffice.test/uslugi", "Aurum Family Office – usługi",
     "2026-10-04", {"3": True}, "Aurum Family Office", None, """
<h1>Aurum Family Office – zarządzamy majątkiem rodzin</h1>
<p>Wealth management dla zamożnych klientów. Indywidualna strategia inwestycyjna i dobór instrumentów finansowych – akcji,
obligacji i funduszy ETF – dopasowany do Twojej sytuacji i profilu ryzyka.</p>
<p>Rekomendujemy zakup i sprzedaż konkretnych spółek oraz prowadzimy przebudowę portfela. Success fee 20% od zysku.
Umów bezpłatną konsultację.</p>
<p>Aurum Family Office sp. z o.o., ul. Złota 1, 00-001 Warszawa, NIP: 000-000-00-00, KRS: 0000000000,
e-mail: kontakt@aurum-familyoffice.test, tel. +48 000 000 000</p>""")

page("doradcy/prime-wealth.html", "https://primewealth-consulting.test/oferta", "Prime Wealth Consulting – oferta",
     "2026-10-10", {"3": True}, "Prime Wealth Consulting", None, """
<h1>Investment consulting – Prime Wealth</h1>
<p>Powiemy Ci, które akcje kupić i kiedy sprzedać. Otrzymasz spersonalizowane rekomendacje inwestycyjne dotyczące spółek z GPW,
przygotowane w oparciu o Twoje cele.</p>
<p>Analiza Twojego portfela i alokacja aktywów. Abonament 490 zł miesięcznie. Skontaktuj się z nami: biuro@primewealth-consulting.test</p>""")

page("doradcy/sygnaly-premium.html", "https://tradersignals-pl.test/premium", "Sygnały Premium – kopiuj moje transakcje",
     "2026-10-18", {"3": True}, "Trader Signals PL", "Marek", """
<h1>Sygnały transakcyjne Premium</h1>
<p>Codzienne sygnały kupna i sprzedaży na kontraktach CFD na indeksy i surowce. Kopiuj moje transakcje i zarabiaj razem ze mną.</p>
<p>Dostęp do grupy VIP – 299 zł miesięcznie. Zapisz się teraz.</p>""")

page("doradcy/goldstar.html", "https://goldstar-capital.test/o-nas", "GoldStar Capital Partners",
     "2026-10-26", {"3": True}, "GoldStar Capital Partners", None, """
<h1>GoldStar Capital Partners</h1>
<p>Zarządzamy kapitałem naszych klientów i inwestujemy w akcje oraz obligacje. Indywidualne rekomendacje inwestycyjne
od naszych analityków. Gwarantujemy 8% miesięcznie.</p><p>Umów spotkanie z doradcą inwestycyjnym.</p>""")

page("doradcy/coach-finansowy.html", "https://twoj-plan-finansowy.test/oferta", "Coaching finansowy – Twój Plan",
     "2026-11-07", {"3": True}, "Twój Plan Finansowy", "Karolina", """
<h1>Indywidualny plan finansowy</h1>
<p>Pomagam uporządkować budżet i oszczędności. W ramach pakietu Premium przygotuję dla Ciebie indywidualny plan inwestycyjny:
dobór funduszy ETF dopasowany do Twojego profilu ryzyka. Pakiet 900 zł.</p>""")

page("doradcy/akademia-etf.html", "https://akademia-etf.test/kurs-podstawy", "Kurs: podstawy ETF – Akademia ETF",
     "2026-10-13", {"3": False}, "Akademia ETF", None, """
<h1>Kurs dla początkujących: czym jest ETF</h1>
<p>Wyjaśniamy, czym są fundusze ETF, jak działa indeks i jak samodzielnie budować portfel. Kurs 199 zł.</p>
<p>Materiał wyłącznie edukacyjny – nie stanowi rekomendacji inwestycyjnej. Nie świadczymy usług doradztwa inwestycyjnego.</p>""")

page("doradcy/kancelaria.html", "https://kancelaria-podatkowa.test/uslugi", "Kancelaria podatkowa – usługi",
     "2026-10-19", {"3": False}, "Kancelaria Podatkowa Nowak", None, """
<h1>Doradztwo podatkowe i księgowość</h1>
<p>Rozliczamy podatek od zysków kapitałowych (PIT-38), w tym z akcji i obligacji zagranicznych. Biuro rachunkowe dla firm.</p>
<p>Indywidualna konsultacja podatkowa – cennik od 150 zł. Umów konsultację.</p>""")

page("doradcy/horyzont.html", "https://horyzont-wealth.test/o-nas", "Horyzont Wealth – o nas",
     "2026-10-24", {"3": False}, "Horyzont Wealth", None, """
<h1>Horyzont Wealth – planowanie finansowe</h1>
<p>Usługi wealth management świadczymy we współpracy z licencjonowanym domem maklerskim, który odpowiada za doradztwo
inwestycyjne. Jesteśmy agentem firmy inwestycyjnej wpisanym do rejestru KNF.</p>""")

page("doradcy/krypto-sygnaly.html", "https://krypto-rakieta.test/vip", "Krypto Rakieta VIP",
     "2026-11-08", {"3": False}, "Krypto Rakieta", None, """
<h1>Grupa VIP – sygnały na kryptowaluty</h1>
<p>Sygnały kupna i sprzedaży bitcoina i altcoinów, indywidualne konsultacje dla członków grupy. Abonament 149 zł miesięcznie.</p>""")

page("doradcy/blog-portfel.html", "https://moj-portfel-dywidendowy.test/listopad", "Mój portfel dywidendowy – listopad",
     "2026-11-09", {"3": False}, "Mój portfel dywidendowy", "Tomek", """
<h1>Mój portfel dywidendowy – listopad</h1>
<p>W tym miesiącu dokupiłem akcje dwóch spółek energetycznych. Moim zdaniem są niedowartościowane, ale nie znam Twojej sytuacji –
to nie jest rekomendacja. Pokazuję tylko, co kupuję do swojego portfela.</p>""")

SOCIAL_ITEMS = {
    "tiktok": [
        {"url": "https://www.tiktok.com/@demo_inwestor_kuba/video/7400000000000000001", "author": "@demo_inwestor_kuba",
         "author_url": "https://www.tiktok.com/@demo_inwestor_kuba", "published_at": "2026-10-06",
         "text": "Jak zarobiłem 5000 zł w tydzień na złocie z NordFX 💰 Link w bio! Kod polecający KUBA500 daje bonus na start.",
         "hashtags": ["#forex", "#nordfx", "#ad", "#pasywnydochod"], "metrics": {"views": 182000, "likes": 9100},
         "ground_truth": {"1": True}},
        {"url": "https://www.tiktok.com/@demo_signals_vip/video/7400000000000000003", "author": "@demo_signals_vip",
         "author_url": "https://www.tiktok.com/@demo_signals_vip", "published_at": "2026-10-22",
         "text": "Chcesz wiedzieć, które akcje kupić? W mojej grupie VIP dostajesz sygnały kupna i sprzedaży oraz indywidualne rekomendacje dopasowane do Twojego portfela. Abonament 199 zł, link w bio.",
         "hashtags": ["#gielda", "#akcje"], "metrics": {"views": 54000}, "ground_truth": {"3": True}},
        {"url": "https://www.tiktok.com/@demo_trader_en/video/7400000000000000004", "author": "@demo_trader_en",
         "author_url": "https://www.tiktok.com/@demo_trader_en", "published_at": "2026-10-30",
         "text": "My favourite broker is NordFX, use my referral code to get a bonus. Trading is fun!",
         "hashtags": ["#trading"], "metrics": {"views": 12000}, "language": "en"},
    ],
    "instagram": [
        {"url": "https://www.instagram.com/p/DEMO_ola_bank/", "author": "@demo_ola_inwestuje",
         "author_url": "https://www.instagram.com/demo_ola_inwestuje/", "published_at": "2026-10-07",
         "caption": "Mój sposób na oszczędzanie 👉 konto maklerskie w Banku Nadwiślańskim. Zarabiaj ze mną! Link w bio, kod OLA bez prowizji. #współpraca #reklama",
         "metrics": {"likes": 3400}, "ground_truth": {"1": True}},
        {"url": "https://www.instagram.com/p/DEMO_vistula_official/", "author": "@vistuladm",
         "author_url": "https://www.instagram.com/vistuladm/", "published_at": "2026-10-28",
         "caption": "Zarabiaj nawet 25% rocznie z Vistula Trade! Bez ryzyka i bez prowizji. Otwórz rachunek już dziś.",
         "metrics": {"likes": 800}, "ground_truth": {"2": True}},
    ],
    "facebook": [
        {"url": "https://www.facebook.com/ads/library/?id=990000000000001", "author": "Inwestuj z Kubą (demo)",
         "author_url": "https://www.facebook.com/demo.inwestuj.z.kuba", "published_at": "2026-10-27",
         "title": "Najlepszy broker CFD 2026",
         "text": "Polecam NordFX – handluję tam od roku. Załóż konto z kodem KUBA i odbierz bonus 500 zł. Post sponsorowany.",
         "links": ["https://nordfx-markets.test/pl/register?ref=kuba"], "metrics": {"eu_total_reach": 41000},
         "ad_meta": {"ad_id": "990000000000001", "platforms": ["facebook", "instagram"]}, "ground_truth": {"1": True}},
        {"url": "https://www.facebook.com/ads/library/?id=990000000000002", "author": "Aurum Family Office (demo)",
         "author_url": "https://www.facebook.com/demo.aurum.fo", "published_at": "2026-11-02",
         "title": "Twój majątek w dobrych rękach",
         "text": "Zarządzamy portfelem inwestycyjnym naszych klientów. Indywidualne rekomendacje inwestycyjne i dobór akcji oraz obligacji dopasowany do Twojej sytuacji. Umów bezpłatną konsultację.",
         "links": ["https://aurum-familyoffice.test/kontakt"], "metrics": {"eu_total_reach": 12000},
         "ad_meta": {"ad_id": "990000000000002", "platforms": ["facebook"]}, "ground_truth": {"3": True}},
        {"url": "https://www.facebook.com/ads/library/?id=990000000000003", "author": "Kopernik Securities S.A.",
         "author_url": "https://www.facebook.com/demo.kopernik", "published_at": "2026-11-05",
         "title": "IKE w Kopernik Securities",
         "text": "Reklama. Oszczędzaj na emeryturę z IKE w Kopernik Securities S.A. Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału. Wartość instrumentów może spaść.",
         "links": ["https://kopernik-securities.test/ike"], "metrics": {"eu_total_reach": 30000},
         "ad_meta": {"ad_id": "990000000000003", "platforms": ["facebook"]}, "ground_truth": {"1": False, "2": False}},
    ],
}


def render_page(path, canonical, title, date, gt, site, author, body, css, viewport, ld) -> str:
    author_meta = f'<meta name="author" content="{h.escape(author)}">' if author else ""
    ld_tag = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if ld else ""
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">{VIEWPORT if viewport else ""}{ld_tag}<title>{h.escape(title)}</title>
<link rel="canonical" href="{canonical}">
<meta property="og:site_name" content="{h.escape(site)}">
<meta property="article:published_time" content="{date}T10:00:00">
{author_meta}
<meta name="iw-ground-truth" content='{json.dumps(gt)}'>
<style>{BASE_CSS}{css}</style></head>
<body>{body}
</body></html>
"""


def main():
    SITES.mkdir(exist_ok=True)
    SOCIAL.mkdir(exist_ok=True)
    pages = P
    links = []
    for p in pages:
        f = SITES / p[0]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(render_page(*p), encoding="utf-8")
        links.append(f'<li><a href="/demo/sites/{p[0]}">{h.escape(p[2])}</a></li>')
    (SITES / "index.html").write_text(
        '<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="robots" content="noindex, follow">'
        "<title>ScopeOnMedia – mini-internet demonstracyjny</title></head><body><h1>Mini-internet demonstracyjny "
        "(fikcyjne podmioty)</h1><ul>" + "\n".join(links) + "</ul></body></html>", encoding="utf-8")
    for platform, items in SOCIAL_ITEMS.items():
        for it in items:
            it["platform"] = platform
        (SOCIAL / f"{platform}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"zapisano {len(pages)} stron i {sum(map(len, SOCIAL_ITEMS.values()))} postów social media")


if __name__ == "__main__":
    main()
