import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmtDateTime, humanize, MODULES, REGISTRY_CATEGORIES, safeHref, SOURCES, STATUSES } from "../constants.js";
import RiskBadge from "./RiskBadge.jsx";
import RulesTable from "./RulesTable.jsx";
import StatusSelect from "./StatusSelect.jsx";

function Field({ label, children }) {
  return (
    <div className="field">
      <div className="field-label">{label}</div>
      <div className="field-value">{children}</div>
    </div>
  );
}

function Reasons({ items, negative }) {
  if (!items.length) return null;
  return (
    <ul className="reasons">
      {items.map((r, i) => (
        <li key={i} className={`reason ${negative ? "neg" : ""}`}>
          <div className="reason-head">
            <span className="reason-rule">{r.rule}</span>
            <span>{r.label}</span>
            {r.weight !== 0 && <span className="reason-w">{r.weight > 0 ? "+" : ""}{r.weight?.toFixed(1)}</span>}
          </div>
          {r.evidence && <div className="reason-ev">„{r.evidence}”</div>}
        </li>
      ))}
    </ul>
  );
}

function Definition({ def }) {
  const items = [
    ["A_personalizacja", "A. Personalizacja (potrzeby / sytuacja klienta)"],
    ["B_rekomendacja", "B. Rekomendacja nabycia / zbycia / trzymania"],
    ["C_instrument_finansowy", "C. Instrument finansowy (art. 2 u.o.i.f.)"],
  ];
  return (
    <div className="req-grid">
      {items.map(([k, l]) => <span key={k} className={`req ${def[k] ? "bad" : "ok"}`}>{def[k] ? "✓" : "–"} {l}</span>)}
    </div>
  );
}

function Screenshots({ docId, available }) {
  const [vp, setVp] = useState(available.includes("desktop") ? "desktop" : available[0]);
  if (!available.length) return null;
  return (
    <>
      <h3>Zrzut ekranu (materiał dowodowy)</h3>
      <div className="seg" role="group" aria-label="Widok">
        {available.map((v) => (
          <button key={v} className={`seg-btn ${vp === v ? "on" : ""}`} onClick={() => setVp(v)}>{v === "phone" ? "Telefon" : "Desktop"}</button>
        ))}
      </div>
      <div className={`shot shot-${vp}`}>
        <img src={api.screenshotUrl(docId, vp)} alt={`Zrzut ekranu – ${vp}`} loading="lazy" />
      </div>
    </>
  );
}

function Similar({ id, onOpen }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    api.similar(id).then(setItems).catch(() => setItems([]));
  }, [id]);
  if (!items || !items.length) return null;
  return (
    <>
      <h3>Podobne materiały (embeddingi)</h3>
      <ul className="similar">
        {items.map((s) => (
          <li key={s.document_id}>
            <span className="sim">{Math.round(s.similarity * 100)}%</span>
            {s.finding ? (
              <button className="linklike" onClick={() => onOpen(s.finding.id)}>{s.title || s.url}</button>
            ) : <span>{s.title || s.url}</span>}
            <span className="muted small"> · {SOURCES[s.source_type] || s.source_type}{s.author ? ` · ${s.author}` : ""}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export default function FindingDrawer({ id, version, onClose, onStatusChange, onOpen }) {
  const [f, setF] = useState(null);
  const [note, setNote] = useState("");
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    api.finding(id).then((d) => {
      if (!alive) return;
      setF(d);
      setNote(d.analyst_note || "");
      setErr(null);
    }).catch((e) => alive && setErr(e.message));
    return () => { alive = false; };
  }, [id, version]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Szczegóły incydentu" role="dialog">
        {err && <div className="error-banner">{err}</div>}
        {!f ? <div className="empty">Ładowanie…</div> : (
          <>
            <div className="drawer-head">
              <div>
                <div className="muted small">{MODULES[f.module].short} · {f.module_name}</div>
                <h2>{humanize(f.category)}</h2>
              </div>
              <div className="row-gap drawer-actions">
                <a className="btn" href={api.evidenceUrl(f.id)} download
                   title="ZIP: raport PDF, zrzuty ekranu, źródło strony i sumy SHA-256">Teczka dowodowa ↓</a>
                <button className="btn ghost" onClick={onClose} aria-label="Zamknij">✕</button>
              </div>
            </div>
            <div className="drawer-scores">
              <RiskBadge level={f.risk_level} score={f.score} />
              <span className="muted small">próg {f.threshold.toFixed(2)}</span>
              <span className="muted small">reguły + embedding: {f.rule_score.toFixed(3)}</span>
              <span className="muted small">LLM: {f.llm_score != null ? f.llm_score.toFixed(3) : (f.llm?.status === "queued" || f.llm?.status === "running" ? "w kolejce…" : "—")}</span>
              {f.ground_truth != null && <span className="muted small">etykieta walidacyjna: {f.ground_truth ? "naruszenie" : "brak naruszenia"}</span>}
            </div>

            <div className="fields">
              <Field label={f.module === 3 ? "Podmiot" : "Firma inwestycyjna"}>
                <span className="strong">{f.firm?.name || "—"}</span>
                {f.firm?.category && <span className="muted small"> · {REGISTRY_CATEGORIES[f.firm.category] || f.firm.category}{f.firm.country ? ` (${f.firm.country})` : ""}</span>}
              </Field>
              {f.module !== 2 && (
                <Field label="Podmiot reklamujący / publikujący">
                  {safeHref(f.advertiser?.url) ? <a href={safeHref(f.advertiser.url)} target="_blank" rel="noreferrer noopener">{f.advertiser.name}</a> : f.advertiser?.name}
                  {f.module === 1 && f.advertiser?.is_labeled_ad === false && <span className="tag warn">nieoznaczona reklama</span>}
                  {f.advertiser?.reach && Object.keys(f.advertiser.reach).length > 0 && (
                    <span className="muted small"> · {Object.entries(f.advertiser.reach).map(([k, v]) => `${k}: ${Number(v).toLocaleString("pl-PL")}`).join(", ")}</span>
                  )}
                </Field>
              )}
              <Field label="Lokalizacja (URL)">
                <a href={safeHref(f.url)} target="_blank" rel="noreferrer noopener" className="url">{f.url}</a>
                {f.fetched_url && f.fetched_url !== f.url && <div className="muted small">pobrano z: {f.fetched_url}</div>}
              </Field>
              <Field label="Publikacja / wykrycie / ostatnio widziane">
                {fmtDateTime(f.published_at)} / {fmtDateTime(f.first_seen_at)} / {fmtDateTime(f.last_seen_at)}
                {f.availability === "removed" && <span className="tag">usunięte</span>}
              </Field>
              {f.module === 3 && f.entity && (
                <Field label="Dane podmiotu">
                  {[["NIP", f.entity.nip], ["KRS", f.entity.krs], ["REGON", f.entity.regon], ["e-mail", f.entity.emails],
                    ["tel.", f.entity.phones], ["adres", f.entity.addresses]].filter(([, v]) => v?.length)
                    .map(([k, v]) => <div key={k} className="small">{k}: {v.join(", ")}</div>)}
                  {!Object.values(f.entity).some((v) => Array.isArray(v) && v.length) && <span className="muted small">brak danych identyfikacyjnych w treści</span>}
                </Field>
              )}
              {f.details?.affiliate_links?.length > 0 && (
                <Field label="Linki afiliacyjne">{f.details.affiliate_links.map((l) => <div key={l} className="url small">{l}</div>)}</Field>
              )}
              {f.near_duplicates?.length > 0 && <Field label="Ten sam przekaz u innych nadawców">{f.near_duplicates.length} materiał(y) – możliwa kampania</Field>}
            </div>

            {f.module === 2 && f.rules?.length > 0 && (
              <>
                <h3>Kryteria informacji o ryzyku (18 reguł)</h3>
                <div className="muted small">Źródło stylów: {f.details?.style_source === "render" ? "renderowanie Playwright (desktop / tablet / telefon)" : f.details?.style_source === "static_css" ? "statyczna analiza CSS" : "tekst"} · przeważająca czcionka {f.details?.predominant_font_px}px</div>
                <RulesTable rules={f.rules} />
              </>
            )}
            {f.module === 3 && f.details?.definition_art76 && (
              <>
                <h3>Elementy definicji doradztwa (art. 76 u.o.i.f.)</h3>
                <Definition def={f.details.definition_art76} />
              </>
            )}

            {f.module !== 2 && (
              <>
                <h3>Sygnały za naruszeniem</h3>
                <Reasons items={f.reasons.filter((r) => r.weight >= 0)} />
                {f.reasons.some((r) => r.weight < 0) && <><h3>Sygnały przeciw</h3><Reasons negative items={f.reasons.filter((r) => r.weight < 0)} /></>}
              </>
            )}
            {f.llm?.status === "done" ? (
              <>
                <h3>Ocena LLM ({f.llm.model}) – p = {f.llm.probability.toFixed(2)}{f.llm.advisory ? " · opinia doradcza" : ` · waga ${f.llm.weight}`}</h3>
                {f.llm.advisory && <p className="muted small">Nie zmienia score: model tekstowy nie widzi prezentacji wizualnej (reguły 4–8 ocenia renderowanie Playwright).</p>}
                <ul className="reasons">{f.llm.reasons.map((r, i) => <li key={i} className="reason llm">{r}</li>)}</ul>
              </>
            ) : (
              <div className="row-gap llm-row">
                {f.llm?.status === "queued" || f.llm?.status === "running" ? (
                  <span className="muted small">Ocena LLM w toku – wynik pojawi się automatycznie.</span>
                ) : (
                  <>
                    <button className="btn ghost small" onClick={() => api.requestLlm(f.id).catch((e) => setErr(e.message))}>
                      Poproś o ocenę LLM
                    </button>
                    <span className="muted small">{f.llm?.status === "unavailable" ? "LLM był niedostępny przy ostatniej próbie." : "Druga opinia lokalnego modelu (Gemma) – asynchronicznie."}</span>
                  </>
                )}
              </div>
            )}

            <Screenshots key={f.document_id} docId={f.document_id} available={f.screenshots || []} />
            <Similar id={f.id} onOpen={onOpen} />

            <h3>Treść materiału</h3>
            <pre className="content">{f.text}</pre>

            <h3>Decyzja analityka</h3>
            <div className="decision">
              <StatusSelect value={f.status} onChange={(s) => onStatusChange(f.id, s, note)} />
              <textarea className="input" rows={3} maxLength={4000} placeholder="Notatka analityka…" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="row-gap">
                <button className="btn" onClick={() => onStatusChange(f.id, "confirmed", note)}>Potwierdź naruszenie</button>
                <button className="btn ghost" onClick={() => onStatusChange(f.id, "false_positive", note)}>Fałszywy alarm</button>
                <button className="btn ghost" onClick={() => onStatusChange(f.id, f.status, note)}>Zapisz notatkę</button>
              </div>
              <p className="muted small">„Potwierdzony” i „Fałszywy alarm” stają się etykietami w Panelu kalibracji.</p>
            </div>
            {f.history?.length > 0 && (
              <>
                <h3>Historia statusu</h3>
                <ul className="history">
                  {f.history.map((h, i) => <li key={i}>{fmtDateTime(h.at)}: {STATUSES[h.old]} → <b>{STATUSES[h.new]}</b>{h.note ? ` – ${h.note}` : ""}</li>)}
                </ul>
              </>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
