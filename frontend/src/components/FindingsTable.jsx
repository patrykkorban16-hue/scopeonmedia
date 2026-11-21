import { fmtDate, humanize, MODULES, SOURCES } from "../constants.js";
import RiskBadge from "./RiskBadge.jsx";
import StatusSelect from "./StatusSelect.jsx";

function Row({ f, selected, onSelect, onStatusChange }) {
  const party = f.module === 1 ? f.advertiser?.name : f.module === 3 ? f.entity?.name : null;
  return (
    <tr className={selected ? "selected" : ""} onClick={() => onSelect(f.id)} tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect(f.id)}>
      <td><RiskBadge level={f.risk_level} score={f.score} /></td>
      <td><span className={`mod mod-${f.module}`}>{MODULES[f.module].short}</span></td>
      <td className="cat">
        {humanize(f.category)}
        {f.module === 2 && f.violations > 0 && <div className="muted small">naruszone reguły: {f.violations}</div>}
        {f.llm_status === "queued" || f.llm_status === "running" ? <div className="muted small">LLM w kolejce…</div> : null}
      </td>
      <td>
        <div className="strong">{f.firm?.name || "—"}</div>
        {party && party !== f.firm?.name && <div className="muted small">{f.module === 1 ? "reklamuje: " : ""}{party}</div>}
      </td>
      <td><div className="excerpt">{f.excerpt}</div></td>
      <td>
        <div>{SOURCES[f.source_type] || f.source_type}{f.availability === "removed" && <span className="tag">usunięte</span>}</div>
        <a className="url small" href={f.url} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}>
          {f.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 40)}
        </a>
      </td>
      <td className="nowrap">{fmtDate(f.event_date)}</td>
      <td><StatusSelect compact value={f.status} onChange={(s) => onStatusChange(f.id, s)} /></td>
    </tr>
  );
}

export default function FindingsTable({ items, total, loading, selectedId, onSelect, onStatusChange, sort, onSort }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Wyniki ({total}){loading && <span className="muted small"> · ładowanie…</span>}</h2>
        <label className="muted small">Sortuj:{" "}
          <select className="input compact" value={sort} onChange={(e) => onSort(e.target.value)}>
            <option value="score">wg ryzyka</option>
            <option value="date">wg daty</option>
            <option value="updated">ostatnio zmienione</option>
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>Ryzyko</th><th>Moduł</th><th>Kategoria</th><th>Firma / podmiot</th><th>Treść</th><th>Lokalizacja</th><th>Data</th><th>Status</th></tr>
          </thead>
          <tbody>
            {items.map((f) => <Row key={f.id} f={f} selected={f.id === selectedId} onSelect={onSelect} onStatusChange={onStatusChange} />)}
            {!loading && items.length === 0 && <tr><td colSpan={8} className="empty">Brak wyników – uruchom skan albo zmień filtry.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
