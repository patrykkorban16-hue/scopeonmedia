import { useState } from "react";
import { api } from "../api.js";

// Ekran logowania – jedno hasło zespołu (IW_DASHBOARD_PASSWORD w .env), sesja w ciasteczku HttpOnly.
export default function Login({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(password);
      setPassword("");
      onSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          <span className="mark" aria-hidden />
          <div>
            <div className="wordmark">ScopeOnMedia</div>
            <div className="kicker">monitoring promocji instrumentów finansowych</div>
          </div>
        </div>
        <label className="login-label" htmlFor="pw">Hasło zespołu</label>
        <input id="pw" className="input" type="password" autoComplete="current-password" autoFocus required
          value={password} onChange={(e) => setPassword(e.target.value)} maxLength={256} />
        {error && <p className="err small" role="alert">{error}</p>}
        <button className="btn" disabled={busy || !password}>{busy ? "Logowanie…" : "Zaloguj"}</button>
      </form>
    </main>
  );
}
