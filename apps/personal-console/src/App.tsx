import type {
  AgentMission,
  DocumentRecord,
  MemoryRecord,
  MissionEvent,
} from "@noosfera/contracts";
import { useState } from "react";

import {
  approveMission,
  createConversation,
  deleteMemory,
  getMission,
  listMemories,
  login,
  sendMessage,
  streamMission,
  uploadDocument,
} from "./api";

const terminal = new Set(["completed", "failed", "rejected", "stopped"]);

export function App() {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("sheily");
  const [password, setPassword] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [remember, setRemember] = useState(false);
  const [mission, setMission] = useState<AgentMission | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refreshMission(activeToken: string, missionId: string) {
    const current = await getMission(activeToken, missionId);
    setMission(current);
    if (terminal.has(current.status)) setBusy(false);
    if (current.status === "completed") setMemories(await listMemories(activeToken));
  }

  async function follow(activeToken: string, missionId: string) {
    await streamMission(activeToken, missionId, (event) => {
      setEvents((current) =>
        current.some((item) => item.sequence === event.sequence)
          ? current
          : [...current, event],
      );
      void refreshMission(activeToken, missionId);
    });
    await refreshMission(activeToken, missionId);
  }

  async function onLogin(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const activeToken = await login(username, password);
      const activeConversation = await createConversation(activeToken);
      setToken(activeToken);
      setConversationId(activeConversation);
      setMemories(await listMemories(activeToken));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo iniciar sesión");
    }
  }

  async function onFiles(files: FileList | null) {
    if (!files || !token) return;
    setBusy(true);
    setError("");
    try {
      const uploaded = await Promise.all(
        Array.from(files).map((file) => uploadDocument(token, file)),
      );
      setDocuments((current) => [...current, ...uploaded]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo subir el documento");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!prompt.trim() || !conversationId) return;
    setBusy(true);
    setError("");
    setEvents([]);
    try {
      const created = await sendMessage(
        token,
        conversationId,
        prompt,
        documents.map((item) => item.id),
        remember,
      );
      setMission(created);
      void follow(token, created.id).catch((reason: Error) => setError(reason.message));
    } catch (reason) {
      setBusy(false);
      setError(reason instanceof Error ? reason.message : "No se pudo crear la misión");
    }
  }

  async function decide(approved: boolean) {
    if (!mission) return;
    setBusy(true);
    setError("");
    try {
      await approveMission(token, mission.id, approved, remember);
      void follow(token, mission.id).catch((reason: Error) => setError(reason.message));
    } catch (reason) {
      setBusy(false);
      setError(reason instanceof Error ? reason.message : "No se pudo registrar la decisión");
    }
  }

  async function forget(memoryId: string) {
    await deleteMemory(token, memoryId);
    setMemories(await listMemories(token));
  }

  if (!token) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <p className="eyebrow">SHEILY · NODO SOBERANO</p>
          <h1>Todo queda aquí.</h1>
          <p>El modelo, los documentos y la memoria permanecen en tu nodo local.</p>
          <form onSubmit={onLogin}>
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
            <button>Entrar en el nodo</button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside>
        <p className="eyebrow">SHEILY 0.2</p>
        <h2>Memoria soberana</h2>
        <p className="muted">Solo se guarda cuando lo autorizas expresamente.</p>
        <div className="memory-list">
          {memories.length === 0 && <small>Sin recuerdos persistentes.</small>}
          {memories.map((memory) => (
            <article key={memory.id}>
              <p>{memory.content.slice(0, 180)}</p>
              <button className="ghost" onClick={() => void forget(memory.id)}>
                Borrar
              </button>
            </article>
          ))}
        </div>
      </aside>
      <section className="workspace">
        <header>
          <div>
            <p className="eyebrow">CONVERSACIÓN LOCAL</p>
            <h1>¿Qué quieres comprender?</h1>
          </div>
          <span className="local-badge">● modelo local</span>
        </header>
        <section className="composer-card">
          <form onSubmit={onSubmit}>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Analiza estos documentos y crea un informe con sus fuentes…"
              rows={6}
            />
            <div className="attachments">
              <label className="file-button">
                Añadir documentos
                <input
                  type="file"
                  multiple
                  accept=".txt,.md,.csv,.pdf"
                  onChange={(event) => void onFiles(event.target.files)}
                />
              </label>
              {documents.map((document) => (
                <span key={document.id}>{document.name}</span>
              ))}
            </div>
            <div className="composer-actions">
              <label className="remember">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(event) => setRemember(event.target.checked)}
                />{" "}
                Recordar el resultado 30 días
              </label>
              <button disabled={busy || !prompt.trim()}>
                {busy ? "Procesando…" : "Crear misión"}
              </button>
            </div>
          </form>
        </section>
        {error && <p className="error banner">{error}</p>}
        {mission && (
          <section className="mission-card">
            <div className="mission-title">
              <div>
                <p className="eyebrow">MISIÓN {mission.status.toUpperCase()}</p>
                <h2>{mission.plan?.objective ?? mission.prompt}</h2>
              </div>
              {mission.risk && (
                <span className={`risk ${mission.risk.risk_class}`}>
                  {mission.risk.risk_class}
                </span>
              )}
            </div>
            {mission.plan && (
              <ol>
                {mission.plan.steps.map((step) => (
                  <li key={step.index}>{step.description}</li>
                ))}
              </ol>
            )}
            {mission.status === "awaiting-approval" && (
              <div className="approval">
                <h3>Tu aprobación es necesaria</h3>
                <p>{mission.risk?.reasons.join(" · ")}</p>
                <div>
                  <button className="danger" onClick={() => void decide(false)}>
                    Rechazar
                  </button>
                  <button onClick={() => void decide(true)}>Autorizar una vez</button>
                </div>
              </div>
            )}
            {mission.result && (
              <article className="result">
                <h3>Resultado verificado</h3>
                <pre>{mission.result.answer}</pre>
                {mission.result.citations.length > 0 && (
                  <footer>
                    Fuentes: {mission.result.citations.map((citation) => citation.label).join(", ")}
                  </footer>
                )}
              </article>
            )}
            {mission.error && <p className="error">{mission.error}</p>}
            <div className="timeline">
              {events.map((event) => (
                <span key={event.sequence}>
                  <b>{event.sequence}</b>
                  {event.event_type}
                </span>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
