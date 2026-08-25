import type { AuditEntry, OperatorStatus } from "@noosfera/contracts";
import { useEffect, useState } from "react";

import { loadAudit, loadStatus, login, setSafeStop } from "./api";

export function App() {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("sheily");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<OperatorStatus | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh(activeToken = token) {
    if (!activeToken) return;
    try {
      const [nextStatus, nextAudit] = await Promise.all([
        loadStatus(activeToken),
        loadAudit(activeToken),
      ]);
      setStatus(nextStatus);
      setAudit(nextAudit);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo actualizar el estado");
    }
  }

  async function onLogin(event: React.FormEvent) {
    event.preventDefault();
    try {
      const activeToken = await login(username, password);
      setToken(activeToken);
      await refresh(activeToken);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo iniciar sesión");
    }
  }

  async function toggleStop() {
    if (!status) return;
    setBusy(true);
    try {
      await setSafeStop(token, !status.stop_active);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cambiar la parada segura");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!token) return undefined;
    const interval = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(interval);
  }, [token]);

  if (!token) {
    return (
      <main className="login-shell">
        <form className="login-card" onSubmit={onLogin}>
          <p>NOOSFERA / CONTROL</p>
          <h1>Acceso operacional</h1>
          <label>
            Usuario
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          <button>Autenticar</button>
          {error && <strong className="error">{error}</strong>}
        </form>
      </main>
    );
  }

  const services = [
    ["Modelo", status?.model_name],
    ["Persistencia", status?.storage_backend],
    ["Eventos", status?.event_bus],
    ["Políticas", status?.policy_engine],
    ["Ejecución", status?.execution_kernel],
  ];

  return (
    <main className="operator-shell">
      <header>
        <div>
          <p>NOOSFERA / CONTROL</p>
          <h1>Estado del nodo soberano</h1>
        </div>
        <button
          className={status?.stop_active ? "resume" : "stop"}
          disabled={busy}
          onClick={() => void toggleStop()}
        >
          {status?.stop_active ? "REANUDAR NODO" : "PARADA SEGURA"}
        </button>
      </header>
      {error && <p className="error banner">{error}</p>}
      <section className="summary">
        <article><b>14</b><span>dominios registrados</span></article>
        <article><b>2</b><span>herramientas Rust permitidas</span></article>
        <article className={status?.stop_active ? "critical" : "healthy"}>
          <b>{status?.stop_active ? "STOP" : "OK"}</b><span>canal de parada</span>
        </article>
      </section>
      <section className="runtime-grid">
        {services.map(([label, value]) => (
          <article key={label}><i /><span>{label}</span><strong>{value ?? "comprobando"}</strong></article>
        ))}
      </section>
      <section className="audit-panel">
        <div className="panel-title"><div><p>AUDITORÍA ENCADENADA</p><h2>Últimos acontecimientos</h2></div><button onClick={() => void refresh()}>Actualizar</button></div>
        <div className="audit-list">
          {audit.length === 0 && <p>Sin acontecimientos registrados.</p>}
          {audit.map((entry) => (
            <article key={entry.receipt_hash}>
              <time>{new Date(entry.created_at).toLocaleString()}</time>
              <strong>{entry.event_type}</strong>
              <span>{entry.mission_id.slice(-12)}</span>
              <code>{entry.receipt_hash.slice(0, 16)}…</code>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
