import { STATUSES } from "../constants.js";

export default function StatusSelect({ value, onChange, compact }) {
  return (
    <select className={`input status-select st-${value} ${compact ? "compact" : ""}`} value={value} aria-label="Status"
      onClick={(e) => e.stopPropagation()} onChange={(e) => onChange(e.target.value)}>
      {Object.entries(STATUSES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
    </select>
  );
}
