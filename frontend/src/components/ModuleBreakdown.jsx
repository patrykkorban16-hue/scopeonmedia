import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COLORS, MODULES, RISKS } from "../constants.js";
import { axisTick, legendProps, tooltipStyle } from "./charts.js";

export default function ModuleBreakdown({ stats }) {
  const data = [1, 2, 3].map((m) => ({
    name: MODULES[m].short + " " + MODULES[m].name,
    high: stats?.by_module?.[m]?.high || 0,
    medium: stats?.by_module?.[m]?.medium || 0,
    low: stats?.by_module?.[m]?.low || 0,
  }));
  return (
    <section className="card">
      <div className="card-head"><h2>Poziom ryzyka wg modułu</h2></div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 12, left: 8, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" horizontal={false} />
          <XAxis type="number" allowDecimals={false} tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={160} tick={{ ...axisTick, fill: "var(--ink)", fontSize: 11 }} axisLine={{ stroke: "var(--ink)" }} tickLine={false} />
          <Tooltip cursor={{ fill: "var(--hover)" }} {...tooltipStyle} />
          <Legend {...legendProps} />
          <Bar dataKey="high" name={RISKS.high} stackId="a" fill={COLORS.high} isAnimationActive={false} />
          <Bar dataKey="medium" name={RISKS.medium} stackId="a" fill={COLORS.medium} isAnimationActive={false} />
          <Bar dataKey="low" name={RISKS.low} stackId="a" fill={COLORS.low} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
