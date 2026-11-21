import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmtDateTime, REGISTRY_CATEGORIES } from "../constants.js";

function RunForm() {
  const [kind, setKind] = useState("web");
  const [value, setValue] = useState("");
  const [platform, setPlatform] = useState("tiktok");
  const [msg, setMsg] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    const body = { kind };
    if (kind === "web" && value) body.url = value.trim();
    if (kind === "urls") body.urls = value.split(/\s+/).filter(Boolean);
    if (kind === "social") Object.assign(body, { platform, query: value || undefined });
    if (kind === "search") body.query = value;
    try {
      const r = await api.runJob(body);
      setMsg({ ok: true, text: `Zlecono: ${r.queued.join(", ") || "nic"}` });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  };
  const needsValue = ["web", "urls", "social", "search"].includes(kind);
  return (
    <form className="run-form" onSubmit={submit}>
      <select className="input" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Rodzaj zadania">
        <option value="web">Crawl WWW</option>
        <option value="urls">Lista adresów (posty, strony)</option>
        <option value="social">API platformy społecznościowej</option>
        <option value="search">Wyszukiwarka</option>
        <option value="recheck">Aktualizacja znanych reklam (M1)</option>
        <option value="reanalyze">Ponowna analiza AI</option>
      </select>
      {kind === "social" && (
        <select className="input" value={platform} onChange={(e) => setPlatform(e.target.value)} aria-label="Platforma">
          <option value="facebook">Meta Ad Library (Facebook/Instagram)</option>
          <option value="instagram">Instagram Graph</option>
          <option value="tiktok">TikTok Research</option>
        </select>
      )}
      {needsValue && (
        <input className="input grow" value={value} onChange={(e) => setValue(e.target.value)} aria-label="Cel"
          placeholder={kind === "web" ? "URL startowy (puste = seeds.json)" : kind === "urls" ? "adresy oddzielone spacją" : "zapytanie (puste = seeds.json)"} />
      )}
      <button className="btn">Dodaj do kolejki</button>
      {msg && <span className={`small ${msg.ok ? "muted" : "err"}`}>{msg.text}</span>}
    </form>
  );
}

function Registry({ version }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    const t = setTimeout(() => api.registry(q, cat).then(setData).catch((e) => setMsg(e.message)), 250);
    return () => clearTimeout(t);
  }, [q, cat, version]);
  const importKnf = async () => {
    try {
      await api.runJob({ kind: "registry", sources: ["knf"] });
      setMsg("Import rejestru KNF zlecony – potrwa kilka minut (≈800 podmiotów).");
    } catch (e) {
      setMsg(e.message);
    }
  };
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Rejestr podmiotów</h2>
          <div className="muted small">wersja {data?.version || "—"} · {Object.entries(data?.counts || {}).map(([k, v]) => `${REGISTRY_CATEGORIES[k] || k}: ${v}`).join(" · ")}</div>
        </div>
        <button className="btn ghost" onClick={importKnf}>Importuj Rejestr Firm Inwestycyjnych KNF</button>
      </div>
      {msg && <div className="muted small">{msg}</div>}
      <div className="filters-row">
        <input className="input grow" placeholder="Szukaj podmiotu…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Szukaj podmiotu" />
        <select className="input" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Kategoria">
          <option value="">wszystkie kategorie</option>
          {Object.entries(REGISTRY_CATEGORIES).filter(([k]) => k !== "brak_w_rejestrze").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Nazwa</th><th>Kategoria</th><th>Zezwolenie</th><th>Kraj</th><th>Domeny / aliasy</th><th>Źródło</th></tr></thead>
          <tbody>
            {(data?.items || []).map((e) => (
              <tr key={e.id}>
                <td className="strong">{e.name}</td>
                <td className="small">{REGISTRY_CATEGORIES[e.category] || e.category}</td>
                <td>{e.authorized ? "tak" : <span className="badge risk-high">brak – ostrzeżenie</span>}</td>
                <td>{e.country}</td>
                <td className="small">{[...e.domains, ...e.aliases].join(", ")}</td>
                <td className="small muted">{e.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function SourcesPanel({ version, lastJob, health }) {
  const [jobs, setJobs] = useState([]);
  useEffect(() => {
    api.jobs().then(setJobs).catch(() => setJobs([]));
  }, [version]);
  // zdarzenie „job” z WebSocketu aktualizuje wiersz bez odpytywania API
  useEffect(() => {
    if (!lastJob) return;
    setJobs((prev) => [lastJob, ...prev.filter((j) => j.id !== lastJob.id)].sort((a, b) => b.id - a.id));
  }, [lastJob]);

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>Kolejka zadań i harmonogram</h2>
          {health && <span className="muted small">kolejka {health.queue.backend} · oczekujące {health.queue.pending ?? "?"} · worker {health.worker.alive ? "aktywny" : "nieaktywny"} · baza {health.db} · storage {health.storage}</span>}
        </div>
        <RunForm />
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>#</th><th>Typ</th><th>Cel</th><th>Status</th><th>Materiały</th><th>Nowe</th><th>Alerty</th><th>Start</th><th>Koniec</th></tr></thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.id}</td><td>{j.kind}</td><td className="url small">{j.target}</td>
                  <td><span className={`job-st ${j.status}`}>{j.status}</span>{j.error && <div className="small err">{j.error}</div>}</td>
                  <td>{j.pages}</td><td>{j.new_documents}</td><td>{j.findings}</td>
                  <td className="nowrap small">{fmtDateTime(j.started_at)}</td><td className="nowrap small">{fmtDateTime(j.finished_at)}</td>
                </tr>
              ))}
              {jobs.length === 0 && <tr><td colSpan={9} className="empty">Brak zadań.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      <Registry version={version} />
    </>
  );
}
