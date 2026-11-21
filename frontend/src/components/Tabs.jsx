export default function Tabs({ tabs, value, onChange }) {
  return (
    <nav className="tabs" role="tablist">
      {tabs.map((t, i) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} className={`tab ${value === t.id ? "active" : ""}`}
          onClick={() => onChange(t.id)}>
          <span className="tab-no">{String(i + 1).padStart(2, "0")}</span>
          {t.label}
        </button>
      ))}
    </nav>
  );
}
