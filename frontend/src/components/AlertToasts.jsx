import { useEffect } from "react";
import { humanize, MODULES } from "../constants.js";

function Toast({ a, onOpen, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(a._key), 20000);
    return () => clearTimeout(t);
  }, [a._key, onDismiss]);
  const who = a.module === 1 ? a.advertiser?.name : a.module === 3 ? a.entity?.name : null;
  return (
    <div className="toast" role="alert">
      <div className="toast-head">
        <span className="badge risk-high">Wysokie ryzyko</span>
        <span className="muted small">{MODULES[a.module].short} · {humanize(a.category)}</span>
        <button className="toast-x" onClick={() => onDismiss(a._key)} aria-label="Zamknij">✕</button>
      </div>
      <div className="strong">{a.firm?.name}{who && who !== a.firm?.name ? ` ← ${who}` : ""}</div>
      <div className="toast-body">{a.excerpt.slice(0, 150)}…</div>
      <button className="btn small" onClick={() => { onOpen(a.id); onDismiss(a._key); }}>Otwórz</button>
    </div>
  );
}

export default function AlertToasts({ alerts, onOpen, onDismiss }) {
  return (
    <div className="toasts" aria-live="polite">
      {alerts.map((a) => <Toast key={a._key} a={a} onOpen={onOpen} onDismiss={onDismiss} />)}
    </div>
  );
}
