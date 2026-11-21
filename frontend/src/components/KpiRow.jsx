import { MODULES } from "../constants.js";

function Kpi({ label, value, hint, tone }) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value ?? "—"}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

export default function KpiRow({ stats, total }) {
  const bm = stats?.by_module || {};
  const high = [1, 2, 3].reduce((a, m) => a + (bm[m]?.high || 0), 0);
  return (
    <section className="kpis" aria-label="Wskaźniki">
      <Kpi label="Incydenty (wg filtrów)" value={total} hint="score ≥ próg modułu" />
      <Kpi label="Wysokie ryzyko" value={stats ? high : null} tone="danger" hint="alerty w czasie rzeczywistym" />
      {[1, 2, 3].map((m) => (
        <Kpi key={m} label={`${MODULES[m].short} · ${MODULES[m].name}`}
          value={stats ? (bm[m]?.high || 0) + (bm[m]?.medium || 0) : null} hint={`z ${bm[m]?.total || 0} ocenionych`} />
      ))}
      <Kpi label="Materiały w bazie" value={stats?.documents} hint={`${stats?.duplicates ?? 0} duplikatów pominiętych`} />
    </section>
  );
}
