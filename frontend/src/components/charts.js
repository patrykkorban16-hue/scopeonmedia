// Wspólne ustawienia wykresów Recharts – Swiss-tech: monospace na osiach, linie włosowe, kwadratowe znaczniki.
import { createElement } from "react";

export const axisTick = { fill: "var(--muted)", fontSize: 10.5, fontFamily: "var(--mono)" };
export const tooltipStyle = {
  contentStyle: {
    background: "var(--surface)", border: "1px solid var(--ink)", borderRadius: 0, color: "var(--ink)",
    fontFamily: "var(--mono)", fontSize: 12, boxShadow: "none",
  },
  labelStyle: { color: "var(--ink)", fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: "var(--ink)", padding: 0 },
};
const legendStyle = { fontSize: 11, fontFamily: "var(--mono)", textTransform: "uppercase", letterSpacing: ".05em" };
// opis serii zawsze w kolorze tekstu – kolor niesie wyłącznie kwadratowy znacznik
export const legendProps = {
  wrapperStyle: legendStyle,
  iconType: "square",
  iconSize: 9,
  formatter: (value) => createElement("span", { style: { color: "var(--ink)" } }, value),
};
