import { MODULES, RISKS, SOURCES, STATUSES } from "../constants.js";

function ChipGroup({ label, options, selected, onToggle }) {
  return (
    <div className="chip-group" role="group" aria-label={label}>
      <span className="chip-label">{label}</span>
      {Object.entries(options).map(([value, text]) => (
        <button key={value} className={`chip ${selected.includes(value) ? "on" : ""}`}
          aria-pressed={selected.includes(value)} onClick={() => onToggle(value)}>
          {text}
        </button>
      ))}
    </div>
  );
}

export default function FilterBar({ filters, onChange, onReset, sources }) {
  const toggle = (key, value) => {
    const cur = filters[key];
    onChange({ ...filters, [key]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value] });
  };
  const sourceOptions = Object.fromEntries((sources.length ? sources : Object.keys(SOURCES)).map((s) => [s, SOURCES[s] || s]));
  const moduleOptions = Object.fromEntries(Object.entries(MODULES).map(([k, m]) => [k, `${m.short} ${m.name}`]));
  return (
    <section className="card filters" aria-label="Filtry">
      <div className="filters-row">
        <input className="input search" placeholder="Szukaj: treść, URL, autor, kategoria…" value={filters.q}
          onChange={(e) => onChange({ ...filters, q: e.target.value })} aria-label="Szukaj" />
        <label className="date">Od
          <input type="date" className="input" value={filters.dateFrom} onChange={(e) => onChange({ ...filters, dateFrom: e.target.value })} />
        </label>
        <label className="date">Do
          <input type="date" className="input" value={filters.dateTo} onChange={(e) => onChange({ ...filters, dateTo: e.target.value })} />
        </label>
        <button className="btn ghost" onClick={onReset}>Wyczyść</button>
      </div>
      <ChipGroup label="Moduł" options={moduleOptions} selected={filters.modules.map(String)} onToggle={(v) => toggle("modules", Number(v))} />
      <ChipGroup label="Ryzyko" options={RISKS} selected={filters.risks} onToggle={(v) => toggle("risks", v)} />
      <ChipGroup label="Źródło" options={sourceOptions} selected={filters.sources} onToggle={(v) => toggle("sources", v)} />
      <ChipGroup label="Status" options={STATUSES} selected={filters.statuses} onToggle={(v) => toggle("statuses", v)} />
    </section>
  );
}
