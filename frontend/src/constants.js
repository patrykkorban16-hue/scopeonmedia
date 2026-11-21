export const MODULES = {
  1: { short: "M1", name: "Ekosystem zewnętrzny", desc: "Reklamy firm inwestycyjnych u finfluencerów i podmiotów trzecich" },
  2: { short: "M2", name: "Zgodność i ryzyko", desc: "Materiały firm inwestycyjnych vs 18 kryteriów art. 44" },
  3: { short: "M3", name: "Shadow advisory", desc: "Doradztwo inwestycyjne bez zezwolenia (art. 76 u.o.i.f.)" },
};

export const RISKS = { high: "Wysokie", medium: "Średnie", low: "Poniżej progu" };

export const STATUSES = {
  new: "Nowy",
  in_review: "W analizie",
  confirmed: "Potwierdzony",
  false_positive: "Fałszywy alarm",
  closed: "Zamknięty",
};

export const SOURCES = {
  web: "WWW",
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
  youtube: "YouTube",
  x: "X",
  linkedin: "LinkedIn",
};

export const REGISTRY_CATEGORIES = {
  dom_maklerski: "Dom maklerski",
  bank_maklerski: "Bank (działalność maklerska)",
  oddzial_zagranicznej_firmy: "Oddział zagranicznej firmy",
  zagraniczna_firma_transgraniczna: "Firma zagraniczna (transgranicznie)",
  ostrzezenie_knf: "Lista ostrzeżeń KNF",
  brak_w_rejestrze: "Brak w rejestrze",
};

// Kolory serii jako zmienne CSS – paleta Swiss-tech (czerń / czerwień sygnałowa / szarość, żółty = średnie ryzyko);
// motyw jasny i ciemny przełącza się w styles.css bez zmian w komponentach.
export const COLORS = {
  m1: "var(--m1)",
  m2: "var(--m2)",
  m3: "var(--m3)",
  high: "var(--risk-high)",
  medium: "var(--risk-medium)",
  low: "var(--risk-low)",
  positive: "var(--accent)",
  negative: "var(--ink)",
  unlabeled: "var(--risk-low)",
  precision: "var(--ink)",
  recall: "var(--accent)",
  f1: "var(--faint)",
};

export const RULE_STATUS = {
  pass: { label: "spełniona", short: "✓" },
  fail: { label: "naruszona", short: "✕" },
  warn: { label: "ostrzeżenie", short: "!" },
  na: { label: "nie dotyczy", short: "–" },
};

// Linki z zebranych materiałów: tylko http(s) – żadnych javascript:, data: itp. (ochrona przed XSS)
export const safeHref = (u) => (typeof u === "string" && /^https?:\/\//i.test(u.trim()) ? u.trim() : undefined);

export const fmtDate =(iso) => (iso ? new Date(iso).toLocaleDateString("pl-PL") : "—");
export const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString("pl-PL") : "—");
export const pct = (x) => `${Math.round((x || 0) * 100)}%`;
// Etykiety kategorii z silnika AI (identyfikatory bez polskich znaków → tekst do wyświetlenia)
const CATEGORY_LABELS = {
  reklama_finfluencer: "Reklama u finfluencera",
  reklama_podmiot_trzeci: "Reklama u podmiotu trzeciego",
  reklama_zagranicznej_firmy_inwestycyjnej: "Reklama zagranicznej firmy inwestycyjnej",
  promocja_podmiotu_z_listy_ostrzezen_KNF: "Promocja podmiotu z listy ostrzeżeń KNF",
  podmiot_z_listy_ostrzezen_KNF: "Podmiot z listy ostrzeżeń KNF",
  doradztwo_inwestycyjne_bez_zezwolenia: "Doradztwo inwestycyjne bez zezwolenia",
  zarzadzanie_portfelem_bez_zezwolenia: "Zarządzanie portfelem bez zezwolenia",
  sygnaly_transakcyjne_bez_zezwolenia: "Sygnały transakcyjne bez zezwolenia",
  poza_art_2_uoif_kryptoaktywa: "Poza art. 2 u.o.i.f. (kryptoaktywa)",
  zgodny: "Zgodny",
};
export const humanize = (s) => CATEGORY_LABELS[s] || (s || "").replaceAll("_", " ");
