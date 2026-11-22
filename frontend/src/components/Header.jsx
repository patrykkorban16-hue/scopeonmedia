import { useState } from "react";
import { api } from "../api.js";

function Indicator({ state, label, value, title }) {
  return (
    <div className="ind" title={title}>
      <span className={`sq ${state}`} aria-hidden />
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

const st = (ok) => (ok === true ? "ok" : ok === false ? "bad" : "off");

// litera „o” w „Scope” jako celownik: pierścień w kolorze tekstu, krzyż w kolorze akcentu
function ScopeO() {
  return (
    <svg className="wm-o" viewBox="0 0 24 24" overflow="visible" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9.35" fill="none" stroke="currentColor" strokeWidth="5.3" />
      <path d="M12 -3.5V27.5M-2.5 12H26.5" stroke="var(--accent)" strokeWidth="2.2" />
    </svg>
  );
}

export default function Header({ connected, health, lastJob, filters, onRun }) {
  const [busy, setBusy] = useState(false);
  const ai = health?.ai_engine;
  const running = lastJob?.status === "running";
  const run = async () => {
    setBusy(true);
    try {
      await onRun();
    } finally {
      setTimeout(() => setBusy(false), 1200);
    }
  };
  return (
    <header className="header">
      <div className="brand">
        <span className="mark" aria-hidden />
        <div>
          <div className="wordmark" role="img" aria-label="ScopeOnMedia">
            <span aria-hidden="true">Sc<ScopeO />peOnMedia</span>
          </div>
          <div className="kicker">monitoring promocji instrumentów finansowych</div>
        </div>
      </div>
      <dl className="status" aria-label="Stan systemu">
        <Indicator state={st(connected)} label="WS" value={connected ? "na żywo" : "offline"} title="Alerty WebSocket (Socket.IO)" />
        <Indicator state={st(health ? health.worker.alive : undefined)} label="Worker" value={health ? (health.worker.alive ? "aktywny" : "brak") : "—"}
          title={health ? `kolejka ${health.queue.backend}, oczekujące ${health.queue.pending ?? "?"}` : ""} />
        <Indicator state={st(ai ? ai.ok : undefined)} label="AI" value={ai?.ok ? "ok" : "—"} title={ai?.embeddings ? `embeddingi: ${ai.embeddings}` : ""} />
        <Indicator state={st(ai?.llm ? ai.llm.available : undefined)} label="LLM" value={ai?.llm?.available ? ai.llm.model : "wył."}
          title={ai?.llm ? `${ai.llm.engine}: ${ai.llm.model}` : ""} />
        <Indicator state={st(health ? health.render : undefined)} label="Render" value={health?.render ? "playwright" : "statyczny"} />
        {running && <Indicator state="run" label="Skan" value={`${lastJob.kind} · ${lastJob.pages}`} />}
      </dl>
      <div className="header-actions">
        <button className="btn" disabled={busy || running} onClick={run}>{running ? "Skan trwa…" : busy ? "Zlecono…" : "Uruchom skan"}</button>
        <a className="btn ghost" href={api.exportUrl(filters, "csv")}>CSV</a>
        <a className="btn ghost" href={api.exportUrl(filters, "json")}>JSON</a>
      </div>
    </header>
  );
}
