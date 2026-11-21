import { RULE_STATUS } from "../constants.js";

// Moduł 2: wynik każdej z 18 reguł z załącznika „kryteria oceny informacji o ryzyku”.
export default function RulesTable({ rules }) {
  const order = { fail: 0, warn: 1, pass: 2, na: 3 };
  const sorted = [...rules].sort((a, b) => order[a.status] - order[b.status]);
  return (
    <table className="table rules">
      <thead><tr><th>Reguła</th><th>Wynik</th><th>Dowód / uzasadnienie</th><th>Podstawa</th></tr></thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.id} className={`rule-${r.status}`}>
            <td><span className="rule-id">{r.id}</span> {r.name}</td>
            <td><span className={`rs rs-${r.status}`}>{RULE_STATUS[r.status].short} {RULE_STATUS[r.status].label}</span></td>
            <td className="small">{r.evidence || ""}</td>
            <td className="small muted nowrap">{r.basis}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
