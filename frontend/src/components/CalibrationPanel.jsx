import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { COLORS, MODULES, pct } from "../constants.js";
import { axisTick, legendProps, tooltipStyle } from "./charts.js";

function Confusion({ c }) {
  const cells = [
    ["TP", c.tp, "trafione naruszenia", "ok"],
    ["FP", c.fp, "fałszywe alarmy", "warn"],
    ["FN", c.fn, "przeoczone naruszenia", "bad"],
    ["TN", c.tn, "poprawnie pominięte", "ok"],
  ];
  return (
    <div className="confusion">
      {cells.map(([k, v, d, tone]) => (
        <div key={k} className={`conf-cell ${tone} ${v > 0 ? "nonzero" : ""}`}>
          <div className="conf-k">{k}</div><div className="conf-v">{v}</div><div className="conf-d">{d}</div>
        </div>
      ))}
    </div>
  );
}

function ModuleCalibration({ module, version, onChanged }) {
  const [data, setData] = useState(null);
  const [thr, setThr] = useState(0.5);
  const [saved, setSaved] = useState(0.5);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    api.calibration(module).then((d) => {
      if (!alive) return;
      setData(d);
      setThr(d.threshold);
      setSaved(d.threshold);
    }).catch((e) => alive && setErr(e.message));
    return () => { alive = false; };
  }, [module, version]);

  // zapis progu 0,5 s po ostatniej zmianie (mysz, klawiatura, dotyk) – bez zalewania API przy przeciąganiu
  useEffect(() => {
    if (!data || Math.abs(thr - saved) < 0.001) return;
    const t = setTimeout(() => {
      api.setThreshold(module, thr)
        .then(() => { setSaved(thr); onChanged(); })
        .catch((e) => setErr(e.message));
    }, 500);
    return () => clearTimeout(t);
  }, [thr, saved, data, module, onChanged]);

  const cur = useMemo(() => data?.curve.reduce((a, c) => (Math.abs(c.threshold - thr) < Math.abs(a.threshold - thr) ? c : a)), [data, thr]);
  if (err) return <div className="error-banner">{err}</div>;
  if (!data || !cur) return <section className="card">Ładowanie…</section>;
  const savedPoint = data.curve.reduce((a, c) => (Math.abs(c.threshold - saved) < Math.abs(a.threshold - saved) ? c : a));
  const delta = (k) => cur[k] - savedPoint[k];

  return (
    <section className="card calib">
      <div className="card-head">
        <h2>{MODULES[module].short} · {MODULES[module].name}</h2>
        <span className="muted small">{data.labeled} etykiet ({data.positives} naruszeń) / {data.total} ocenionych · najlepsze F1 przy {data.best_f1_threshold.toFixed(2)}</span>
      </div>
      <div className="slider-row">
        <label htmlFor={`thr-${module}`}>Próg</label>
        <input id={`thr-${module}`} type="range" min={0} max={1} step={0.01} value={thr}
          onChange={(e) => setThr(Number(e.target.value))} />
        <span className="thr-value">{thr.toFixed(2)}</span>
      </div>
      <div className="calib-metrics">
        <div className="metric"><span>Flagowane</span><b>{cur.flagged}</b></div>
        <div className="metric"><span>Precyzja</span><b>{pct(cur.precision)}</b></div>
        <div className="metric"><span>Pełność</span><b>{pct(cur.recall)}</b></div>
        <div className="metric"><span>F1</span><b>{cur.f1.toFixed(2)}</b></div>
        {Math.abs(thr - saved) >= 0.001 && (
          <span className="muted small">vs zapisany {saved.toFixed(2)}: FP {delta("fp") >= 0 ? "+" : ""}{delta("fp")}, FN {delta("fn") >= 0 ? "+" : ""}{delta("fn")}</span>
        )}
        <button className="btn ghost small" onClick={() => setThr(data.best_f1_threshold)}>Ustaw najlepsze F1</button>
      </div>
      <Confusion c={cur} />
      <div className="grid-2">
        <div>
          <div className="chart-title">Precyzja i pełność w funkcji progu</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.curve} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="threshold" type="number" domain={[0, 1]} tick={axisTick} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 1]} tick={axisTick} tickLine={false} axisLine={false} tickFormatter={pct} />
              <Tooltip formatter={(v) => pct(v)} labelFormatter={(l) => `próg ${Number(l).toFixed(2)}`} {...tooltipStyle} />
              <Legend {...legendProps} />
              <Line type="stepAfter" dataKey="precision" name="Precyzja" stroke={COLORS.precision} dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="stepAfter" dataKey="recall" name="Pełność" stroke={COLORS.recall} dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="stepAfter" dataKey="f1" name="F1" stroke={COLORS.f1} dot={false} strokeDasharray="4 3" isAnimationActive={false} />
              <ReferenceLine x={thr} stroke="var(--accent)" strokeDasharray="3 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div className="chart-title">Rozkład score (etykiety walidacyjne + decyzje analityków)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.histogram} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="bin" tick={axisTick} tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: "var(--hover)" }} {...tooltipStyle} />
              <Legend {...legendProps} />
              <Bar dataKey="positive" name="Naruszenie" stackId="a" fill={COLORS.positive} isAnimationActive={false} />
              <Bar dataKey="negative" name="Brak naruszenia" stackId="a" fill={COLORS.negative} isAnimationActive={false} />
              <Bar dataKey="unlabeled" name="Bez etykiety" stackId="a" fill={COLORS.unlabeled} isAnimationActive={false} />
              <ReferenceLine x={(Math.min(0.9, Math.floor(thr * 10) / 10)).toFixed(1)} stroke="var(--accent)" strokeDasharray="3 3" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}

export default function CalibrationPanel({ version, onChanged }) {
  return [1, 2, 3].map((m) => <ModuleCalibration key={m} module={m} version={version} onChanged={onChanged} />);
}
