import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COLORS, MODULES } from "../constants.js";
import { axisTick, legendProps, tooltipStyle } from "./charts.js";

function Segmented({ value, options, onChange, label }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, l]) => (
        <button key={v} className={`seg-btn ${value === v ? "on" : ""}`} aria-pressed={value === v} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

export default function TrendChart({ data, granularity, onGranularity, dateField, onDateField }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Wykryte incydenty w czasie</h2>
        <div className="row-gap">
          <Segmented label="Data" value={dateField} onChange={onDateField}
            options={[["event", "Publikacja"], ["detected", "Wykrycie"]]} />
          <Segmented label="Okres" value={granularity} onChange={onGranularity} options={[["day", "Dzień"], ["week", "Tydzień"]]} />
        </div>
      </div>
      {data.length === 0 ? (
        <div className="empty">Brak incydentów dla wybranych filtrów.</div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="date" tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(d) => d.slice(5)} minTickGap={14} />
            <YAxis allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} />
            <Tooltip cursor={{ fill: "var(--hover)" }} {...tooltipStyle} />
            <Legend {...legendProps} />
            {[1, 2, 3].map((m) => (
              <Bar key={m} dataKey={`m${m}`} name={`${MODULES[m].short} ${MODULES[m].name}`} stackId="s" fill={COLORS[`m${m}`]}
                stroke="var(--surface)" strokeWidth={1} maxBarSize={26} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
