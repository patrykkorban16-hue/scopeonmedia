import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmtDate, humanize, MODULES, REGISTRY_CATEGORIES, RULE_STATUS, SOURCES } from "../constants.js";
import RiskBadge from "./RiskBadge.jsx";

function useReport(module, version) {
  const [state, setState] = useState({ module: null, data: null, error: null });
  useEffect(() => {
    let alive = true;
    api.report(module).then((data) => alive && setState({ module, data, error: null }))
      .catch((e) => alive && setState({ module, data: null, error: e.message }));
    return () => { alive = false; };
  }, [module, version]);
  // dane innego modułu (w trakcie przełączania) nie są renderowane
  return state.module === module ? state : { data: null, error: null };
}

function M1Report({ data, onOpen }) {
  if (!data.length) return <div className="empty">Brak reklam powyżej progu.</div>;
  return data.map((g) => (
    <section key={g.name} className="card">
      <div className="card-head">
        <div>
          <h2>{g.name}</h2>
          <div className="muted small">{REGISTRY_CATEGORIES[g.firm?.category] || g.firm?.category} {g.firm?.country ? `· ${g.firm.country}` : ""}</div>
        </div>
        <div className="row-gap small">
          <span className="tag">{g.ads} reklam</span>
          <span className="tag">{g.advertisers.length} reklamujących</span>
          {g.unlabeled > 0 && <span className="tag warn">{g.unlabeled} bez oznaczenia</span>}
        </div>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Podmiot reklamujący</th><th>Platforma</th><th>Reklama (URL)</th><th>Ryzyko</th><th>Oznaczona</th><th>Afiliacja</th><th>Wykryto / ost. widziana</th></tr></thead>
          <tbody>
            {g.advertisers.flatMap((a) => a.ads.map((ad, i) => (
              <tr key={ad.finding_id} onClick={() => onOpen(ad.finding_id)}>
                <td>{i === 0 ? (a.url ? <a href={a.url} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}>{a.name}</a> : a.name) : ""}</td>
                <td>{SOURCES[a.platform] || a.platform}</td>
                <td className="url small">{ad.url}</td>
                <td><RiskBadge level={ad.risk_level} score={ad.score} /></td>
                <td>{ad.labeled ? "tak" : <span className="tag warn">nie</span>}</td>
                <td>{ad.affiliate ? "link afiliacyjny" : "—"}</td>
                <td className="nowrap small">{fmtDate(ad.first_seen_at)} / {fmtDate(ad.last_seen_at)}{ad.availability === "removed" && <span className="tag">usunięta</span>}</td>
              </tr>
            )))}
          </tbody>
        </table>
      </div>
    </section>
  ));
}

function M2Report({ data, onOpen }) {
  const ids = data.rules.length ? data.rules.map((r) => r.id) : [...new Set(data.items.flatMap((i) => Object.keys(i.rules)))];
  const names = Object.fromEntries(data.rules.map((r) => [r.id, `${r.name} – ${r.basis}`]));
  return (
    <section className="card">
      <div className="card-head">
        <h2>Materiały firm inwestycyjnych × kryteria informacji o ryzyku</h2>
        <div className="legend-inline small">
          {["fail", "warn", "pass", "na"].map((s) => <span key={s}><span className={`cell cell-${s}`}>{RULE_STATUS[s].short}</span> {RULE_STATUS[s].label}</span>)}
        </div>
      </div>
      <div className="table-wrap">
        <table className="table matrix">
          <thead>
            <tr>
              <th>Materiał</th><th>Ryzyko</th>
              {ids.map((id) => <th key={id} title={names[id]} className="mcol">{id}</th>)}
            </tr>
            <tr className="muted small">
              <th>naruszenia (flagowane)</th><th />
              {ids.map((id) => <th key={id} className="mcol">{data.fail_counts[id] || ""}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.items.map((it) => (
              <tr key={it.finding_id} onClick={() => onOpen(it.finding_id)}>
                <td><div className="strong small">{it.firm}</div><div className="url small muted">{it.url.replace(/^https?:\/\//, "")}</div></td>
                <td><RiskBadge level={it.risk_level} score={it.score} /></td>
                {ids.map((id) => {
                  const st = it.rules[id] || "na";
                  return <td key={id} className="mcol"><span className={`cell cell-${st}`} title={`${names[id] || id}: ${RULE_STATUS[st].label}`}>{RULE_STATUS[st].short}</span></td>;
                })}
              </tr>
            ))}
            {data.items.length === 0 && <tr><td colSpan={ids.length + 2} className="empty">Brak materiałów firm inwestycyjnych.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function M3Report({ data, onOpen }) {
  return (
    <section className="card">
      <div className="card-head"><h2>Podmioty podejrzewane o doradztwo inwestycyjne bez zezwolenia</h2></div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Podmiot</th><th>Kategoria</th><th>Ryzyko</th><th>Dane identyfikacyjne</th><th>Definicja art. 76 (A/B/C)</th><th>Treść oferty</th><th>URL</th></tr></thead>
          <tbody>
            {data.map((e) => (
              <tr key={e.finding_id} onClick={() => onOpen(e.finding_id)}>
                <td className="strong">{e.entity?.name || e.domain}{e.on_warning_list && <span className="tag warn">lista ostrzeżeń KNF</span>}</td>
                <td className="small">{humanize(e.category)}</td>
                <td><RiskBadge level={e.risk_level} score={e.score} /></td>
                <td className="small">{[...(e.entity?.nip || []).map((x) => `NIP ${x}`), ...(e.entity?.krs || []).map((x) => `KRS ${x}`), ...(e.entity?.emails || [])].join(", ") || "—"}</td>
                <td className="nowrap">
                  {["A_personalizacja", "B_rekomendacja", "C_instrument_finansowy"].map((k) => (
                    <span key={k} className={`cell ${e.definition?.[k] ? "cell-fail" : "cell-na"}`} title={k}>{k[0]}</span>
                  ))}
                </td>
                <td><div className="excerpt">{e.excerpt}</div></td>
                <td className="url small">{e.url}</td>
              </tr>
            ))}
            {data.length === 0 && <tr><td colSpan={7} className="empty">Brak podmiotów powyżej progu.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ReportsPanel({ version, onOpen }) {
  const [m, setM] = useState(1);
  const { data, error } = useReport(m, version);
  return (
    <>
      <section className="card intro">
        <div className="card-head">
          <div>
            <h2>{MODULES[m].short} · {MODULES[m].name}</h2>
            <div className="muted small">{MODULES[m].desc}</div>
          </div>
          <div className="row-gap">
            <div className="seg" role="group" aria-label="Moduł">
              {[1, 2, 3].map((x) => <button key={x} className={`seg-btn ${m === x ? "on" : ""}`} onClick={() => setM(x)}>{MODULES[x].short}</button>)}
            </div>
            <a className="btn ghost small" href={api.exportUrl({ modules: [m], risks: ["high", "medium"], statuses: [] }, "csv")}>Eksport CSV</a>
          </div>
        </div>
      </section>
      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="empty">Ładowanie…</div>}
      {data && m === 1 && <M1Report data={data} onOpen={onOpen} />}
      {data && m === 2 && <M2Report data={data} onOpen={onOpen} />}
      {data && m === 3 && <M3Report data={data} onOpen={onOpen} />}
    </>
  );
}
