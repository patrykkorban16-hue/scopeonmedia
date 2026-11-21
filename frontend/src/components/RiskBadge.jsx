import { RISKS } from "../constants.js";

export default function RiskBadge({ level, score }) {
  return (
    <span className={`badge risk-${level}`} title={score !== undefined ? `score ${score.toFixed(3)}` : undefined}>
      {RISKS[level]?.split(" ")[0] || level}
      {score !== undefined && <span className="badge-score">{Math.round(score * 100)}</span>}
    </span>
  );
}
