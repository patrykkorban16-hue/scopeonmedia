// Warstwa REST nad API backendu. Wszystkie błędy zwracane jako wyjątki z czytelnym komunikatem.
const BASE = import.meta.env.VITE_API_URL || "";

export function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.append(k, v);
  });
  return p.toString();
}

async function req(path, opts = {}) {
  let r;
  try {
    r = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, ...opts });
  } catch {
    throw new Error("API niedostępne – sprawdź, czy backend działa");
  }
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
    } catch {
      /* odpowiedź bez JSON */
    }
    throw new Error(detail);
  }
  return r.json();
}

export const filterParams = (f) => ({
  module: f.modules,
  source: f.sources,
  risk: f.risks,
  status: f.statuses,
  date_from: f.dateFrom,
  date_to: f.dateTo,
  q: f.q,
  date_field: f.dateField,
});

export const api = {
  findings: (f, sort) => req(`/api/findings?${qs({ ...filterParams(f), sort, limit: 300 })}`),
  finding: (id) => req(`/api/findings/${id}`),
  similar: (id) => req(`/api/findings/${id}/similar`),
  requestLlm: (id) => req(`/api/findings/${id}/llm`, { method: "POST" }),
  setStatus: (id, status, note) =>
    req(`/api/findings/${id}`, { method: "PATCH", body: JSON.stringify({ status, note }) }),
  stats: (f) => req(`/api/stats?${qs({ ...filterParams(f), risk: undefined })}`),
  trends: (f, granularity) => req(`/api/trends?${qs({ ...filterParams(f), granularity })}`),
  calibration: (m) => req(`/api/calibration/${m}`),
  setThreshold: (m, value) => req(`/api/thresholds/${m}`, { method: "PUT", body: JSON.stringify({ value }) }),
  report: (m) => req(`/api/reports/m${m}`),
  jobs: () => req(`/api/jobs`),
  runJob: (body) => req(`/api/jobs`, { method: "POST", body: JSON.stringify(body) }),
  registry: (q, category) => req(`/api/registry?${qs({ q, category, limit: 300 })}`),
  health: () => req(`/api/health`),
  screenshotUrl: (docId, vp) => `${BASE}/api/documents/${docId}/screenshot/${vp}`,
  evidenceUrl: (id) => `${BASE}/api/findings/${id}/evidence`,
  exportUrl: (f, fmt) => `${BASE}/api/export?${qs({ module: f.modules, risk: f.risks, status: f.statuses, fmt })}`,
};

export const SOCKET_URL = BASE || window.location.origin;
