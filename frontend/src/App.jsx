import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { useSocket } from "./useSocket.js";
import Header from "./components/Header.jsx";
import Tabs from "./components/Tabs.jsx";
import FilterBar from "./components/FilterBar.jsx";
import KpiRow from "./components/KpiRow.jsx";
import TrendChart from "./components/TrendChart.jsx";
import ModuleBreakdown from "./components/ModuleBreakdown.jsx";
import FindingsTable from "./components/FindingsTable.jsx";
import FindingDrawer from "./components/FindingDrawer.jsx";
import ReportsPanel from "./components/ReportsPanel.jsx";
import CalibrationPanel from "./components/CalibrationPanel.jsx";
import SourcesPanel from "./components/SourcesPanel.jsx";
import AlertToasts from "./components/AlertToasts.jsx";
import PageTitle from "./components/PageTitle.jsx";
import Login from "./components/Login.jsx";

const DEFAULT_FILTERS = {
  modules: [],
  sources: [],
  risks: ["high", "medium"],
  statuses: [],
  dateFrom: "",
  dateTo: "",
  q: "",
  dateField: "event",
};

const TABS = [
  { id: "incidents", label: "Incydenty" },
  { id: "reports", label: "Raporty modułów" },
  { id: "calibration", label: "Panel kalibracji" },
  { id: "sources", label: "Źródła, zadania, rejestr" },
];

// Bramka logowania: dashboard (z WebSocketem i zapytaniami) montuje się dopiero po zalogowaniu.
export default function App() {
  const [authed, setAuthed] = useState(null);       // null = sprawdzanie sesji

  useEffect(() => {
    api.me().then((r) => setAuthed(Boolean(r.authenticated))).catch(() => setAuthed(false));
    const onUnauthorized = () => setAuthed(false);
    window.addEventListener("iw:unauthorized", onUnauthorized);
    return () => window.removeEventListener("iw:unauthorized", onUnauthorized);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAuthed(false);
    }
  }, []);

  if (authed === null) return <div className="empty">Ładowanie…</div>;
  if (!authed) return <Login onSuccess={() => setAuthed(true)} />;
  return <Dashboard onLogout={logout} />;
}

function Dashboard({ onLogout }) {
  const [tab, setTab] = useState("incidents");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [sort, setSort] = useState("score");
  const [granularity, setGranularity] = useState("day");
  const [data, setData] = useState({ findings: { total: 0, items: [] }, stats: null, trends: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [health, setHealth] = useState(null);
  const [version, setVersion] = useState(0);          // licznik odświeżeń wywoływanych zdarzeniami
  const [lastJob, setLastJob] = useState(null);
  const debounce = useRef(null);

  const refresh = useCallback(() => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => setVersion((v) => v + 1), 350);
  }, []);

  // wyszukiwanie tekstowe z opóźnieniem, pozostałe filtry natychmiast
  const [appliedFilters, setAppliedFilters] = useState(filters);
  useEffect(() => {
    const t = setTimeout(() => setAppliedFilters(filters), filters.q !== appliedFilters.q ? 300 : 0);
    return () => clearTimeout(t);
  }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.findings(appliedFilters, sort), api.stats(appliedFilters), api.trends(appliedFilters, granularity)])
      .then(([findings, stats, trends]) => {
        if (cancelled) return;
        setData({ findings, stats, trends });
        setError(null);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [appliedFilters, sort, granularity, version]);

  useEffect(() => {
    const load = () => api.health().then(setHealth).catch(() => setHealth(null));
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  const connected = useSocket({
    alert: (a) => {
      setAlerts((prev) => [{ ...a, _key: `${a.id}-${Date.now()}` }, ...prev].slice(0, 3));
      refresh();
    },
    finding_updated: refresh,
    thresholds: refresh,
    job: (j) => {
      setLastJob(j);
      if (j.status !== "running") refresh();
    },
    registry: refresh,
  });

  const dismissAlert = useCallback((key) => setAlerts((a) => a.filter((x) => x._key !== key)), []);
  const openFromAlert = useCallback((id) => {
    setTab("incidents");
    setSelectedId(id);
  }, []);

  const onStatusChange = useCallback(async (id, status, note) => {
    try {
      await api.setStatus(id, status, note);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }, [refresh]);

  const th = data.stats?.thresholds;

  return (
    <div className="app">
      <Header connected={connected} health={health} lastJob={lastJob} filters={appliedFilters} onLogout={onLogout}
        onRun={() => api.runJob({ kind: "all" }).catch((e) => setError(e.message))} />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button className="btn ghost small" onClick={() => setError(null)}>Zamknij</button>
        </div>
      )}

      {tab === "incidents" && (
        <main className="page">
          <PageTitle title="Incydenty"
            lede="Materiały z sieci i mediów społecznościowych ocenione przez moduły M1–M3. Score ≥ próg modułu = incydent."
            meta={<><b>{data.findings.total}</b> wyników<br />progi {th ? `M1 ${th[1].toFixed(2)} · M2 ${th[2].toFixed(2)} · M3 ${th[3].toFixed(2)}` : "—"}</>} />
          <FilterBar filters={filters} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)}
            sources={data.stats?.sources || []} />
          <KpiRow stats={data.stats} total={data.findings.total} />
          <div className="grid-2">
            <TrendChart data={data.trends} granularity={granularity} onGranularity={setGranularity}
              dateField={filters.dateField} onDateField={(v) => setFilters({ ...filters, dateField: v })} />
            <ModuleBreakdown stats={data.stats} />
          </div>
          <FindingsTable items={data.findings.items} total={data.findings.total} loading={loading}
            selectedId={selectedId} onSelect={setSelectedId} onStatusChange={onStatusChange} sort={sort} onSort={setSort} />
        </main>
      )}
      {tab === "reports" && (
        <main className="page">
          <PageTitle title="Raporty modułów" lede="Zestawienia wymagane w specyfikacji: M1 firma × reklamujący, M2 materiał × 18 kryteriów, M3 podmioty bez zezwolenia."
            meta="eksport CSV / JSON" />
          <ReportsPanel version={version} onOpen={setSelectedId} />
        </main>
      )}
      {tab === "calibration" && (
        <main className="page">
          <PageTitle title="Panel kalibracji"
            lede="Próg decyduje, od jakiego score materiał staje się incydentem. Niższy próg: mniej przeoczeń (FN), więcej fałszywych alarmów (FP). Zmiana zapisuje się automatycznie i odświeża wszystkie dashboardy."
            meta="etykiety: zbiór walidacyjny + decyzje analityków" />
          <CalibrationPanel version={version} onChanged={refresh} />
        </main>
      )}
      {tab === "sources" && (
        <main className="page">
          <PageTitle title="Źródła i rejestr" lede="Kolejka zadań, harmonogram (cron) i rejestr podmiotów KNF."
            meta={health ? <>kolejka <b>{health.queue.backend}</b> · baza <b>{health.db}</b> · storage <b>{health.storage}</b></> : null} />
          <SourcesPanel version={version} lastJob={lastJob} health={health} />
        </main>
      )}

      {selectedId && (
        <FindingDrawer id={selectedId} version={version} onClose={() => setSelectedId(null)}
          onStatusChange={onStatusChange} onOpen={setSelectedId} />
      )}
      <AlertToasts alerts={alerts} onOpen={openFromAlert} onDismiss={dismissAlert} />
    </div>
  );
}
