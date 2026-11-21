// Tytuł strony w układzie szwajcarskim: duży nagłówek, lead, metadane w monospace po prawej.
export default function PageTitle({ title, lede, meta }) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {meta && <div className="meta">{meta}</div>}
    </div>
  );
}
