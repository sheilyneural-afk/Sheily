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

const statusLabels: Record<string, string> = {
  received: "Petición recibida",
  planning: "Preparando un plan",
  "awaiting-approval": "Esperando tu autorización",
  authorized: "Plan autorizado",
  executing: "Ejecutando en entorno protegido",
  verifying: "Verificando el resultado",
  completed: "Completada",
  rejected: "Rechazada",
  failed: "Fallida",
  stopped: "Detenida de forma segura",
};

const eventLabels: Record<string, string> = {
  "mission.received": "Petición recibida",
  "mission.planning": "Planificación iniciada",
  "phase.cognition.completed": "Análisis cognitivo completado",
  "phase.agency.completed": "Plan vinculado a la petición",
  "phase.governance-evaluation.completed": "Riesgo y permisos evaluados",
  "mission.plan-ready": "Plan preparado",
  "mission.approval-required": "Autorización solicitada",
  "mission.approved-by-user": "Autorizado por ti",
  "mission.self-model-observed": "Estado operativo comprobado",
  "mission.self-answer-grounded": "Respuesta propia vinculada a evidencia",
  "mission.evidence-context-built": "Evidencia estructurada y límites localizados",
  "phase.language-realization.completed": "Borrador local generado",
  "phase.independent-document-verification.completed": "Afirmaciones verificadas por Auditoría",
  "mission.evidence-bundle-sealed": "Paquete de evidencia sellado",
  "mission.capability-issued": "Permiso limitado emitido",
  "mission.executing": "Ejecución protegida iniciada",
  "phase.rust-execution.completed": "Ejecución Rust completada",
  "mission.verifying": "Verificación final iniciada",
  "mission.completed": "Misión completada",
  "mission.rejected-by-user": "Misión rechazada por ti",
  "mission.failed": "La misión falló",
};

const riskLabels: Record<string, string> = {
  R0: "Sin acceso adicional",
  R1: "Requiere tu permiso",
  R2: "Riesgo moderado",
  R3: "Riesgo alto",
  R4: "Riesgo crítico",
  R5: "Operación no autorizable aquí",
};

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
  const [decisionPending, setDecisionPending] = useState<"approved" | "rejected" | null>(null);
  const [error, setError] = useState("");

  async function refreshMission(activeToken: string, missionId: string) {
    const current = await getMission(activeToken, missionId);
    setMission(current);
    if (terminal.has(current.status)) setBusy(false);
    if (current.status === "completed") setMemories(await listMemories(activeToken));
    return current;
  }

  async function follow(activeToken: string, missionId: string) {
    try {
      await streamMission(activeToken, missionId, (event) => {
        setEvents((current) =>
          current.some((item) => item.sequence === event.sequence)
            ? current
            : [...current, event],
        );
        void refreshMission(activeToken, missionId);
      });
    } catch {
      // SSE can be interrupted by a tunnel or reverse proxy while the mission
      // continues safely on the server. Polling below recovers the result.
    }

    const deadline = Date.now() + 5 * 60 * 1000;
    while (Date.now() < deadline) {
      const current = await refreshMission(activeToken, missionId);
      if (terminal.has(current.status)) return;
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    }
    setBusy(false);
    throw new Error("La misión sigue activa; vuelve a consultarla en unos minutos");
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
    setDecisionPending(null);
    try {
      const created = await sendMessage(
        token,
        conversationId,
        prompt,
        documents.map((item) => item.id),
        remember,
      );
      setMission(created);
      void follow(token, created.id).catch((reason: Error) => {
        setBusy(false);
        setError(reason.message);
      });
    } catch (reason) {
      setBusy(false);
      setError(reason instanceof Error ? reason.message : "No se pudo crear la misión");
    }
  }

  async function decide(approved: boolean) {
    if (!mission) return;
    setBusy(true);
    setDecisionPending(approved ? "approved" : "rejected");
    setError("");
    try {
      await approveMission(token, mission.id, approved, remember);
      void follow(token, mission.id).catch((reason: Error) => {
        setBusy(false);
        setError(reason.message);
      });
    } catch (reason) {
      setBusy(false);
      setDecisionPending(null);
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
        <p className="eyebrow">SHEILY 0.3</p>
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
                <p className="eyebrow">MISIÓN · {statusLabels[mission.status]}</p>
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
            {mission.status === "awaiting-approval" && decisionPending === null && (
              <div className="approval">
                <p className="eyebrow">{riskLabels[mission.risk?.risk_class ?? "R1"]}</p>
                <h3>Sheily está esperando tu decisión</h3>
                <p>La misión todavía no ha procesado el contenido ni ha creado el informe.</p>
                <p>Si autorizas este plan, permites únicamente:</p>
                <ul>
                  <li>
                    Leer {documents.length === 1 ? "el documento" : "los documentos"}{" "}
                    {documents.map((document) => document.name).join(", ")}.
                  </li>
                  <li>Entregar su contenido al modelo Ollama que se ejecuta en este nodo.</li>
                  <li>Generar el informe indicado arriba sin acceso a Internet ni efectos externos.</li>
                  {remember && <li>Conservar el resultado autorizado durante 30 días.</li>}
                </ul>
                {mission.risk?.reasons.length ? (
                  <p className="approval-reason">Motivo: {mission.risk.reasons.join(" · ")}</p>
                ) : null}
                <p className="approval-scope">
                  El permiso sirve una sola vez, queda ligado a esta misión y no autoriza otros
                  archivos ni otras acciones.
                </p>
                <div>
                  <button className="danger" onClick={() => void decide(false)}>
                    No autorizar
                  </button>
                  <button onClick={() => void decide(true)}>Autorizar este plan una vez</button>
                </div>
              </div>
            )}
            {mission.status === "awaiting-approval" && decisionPending !== null && (
              <div className="approval approval-recorded" role="status">
                <p className="eyebrow">
                  {decisionPending === "approved" ? "DECISIÓN ENVIADA" : "RECHAZO ENVIADO"}
                </p>
                <h3>
                  {decisionPending === "approved"
                    ? "Autorización registrada; procesando con el modelo local"
                    : "Rechazo registrado; cerrando la misión"}
                </h3>
                <p>No necesitas volver a pulsar ningún botón.</p>
              </div>
            )}
            {mission.result && (
              <article className="result">
                <div className="verification-heading">
                  <div>
                    <p className="eyebrow">INFORME EPISTÉMICO</p>
                    <h3>Resultado con procedencia verificable</h3>
                  </div>
                  {mission.result.verification_report && (
                    <span className="proof-badge">
                      Firma {mission.result.verification_report.key_id}
                    </span>
                  )}
                </div>
                <pre>{mission.result.answer}</pre>
                {mission.result.claims.length > 0 && (
                  <section className="evidence-section">
                    <h4>Afirmaciones que superaron la verificación</h4>
                    <div className="claim-grid">
                      {mission.result.claims.map((claim) => (
                        <article key={claim.id} className="claim-card">
                          <p>{claim.statement}</p>
                          <small>
                            {claim.epistemic_status.replaceAll("-", " ")} · confianza{" "}
                            {Math.round(claim.confidence * 100)}% · {claim.evidence_ids.join(", ")}
                          </small>
                        </article>
                      ))}
                    </div>
                  </section>
                )}
                {mission.result.limitations.length > 0 && (
                  <section className="evidence-section warning-section">
                    <h4>Límites que Sheily no permite ocultar</h4>
                    <ul>
                      {mission.result.limitations.map((item) => (
                        <li key={item.id}>
                          {item.statement}{" "}
                          {item.system_detected && <strong>Detectado por el sistema</strong>}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {mission.result.unknowns.length > 0 && (
                  <section className="evidence-section unknown-section">
                    <h4>No comprobado</h4>
                    <ul>{mission.result.unknowns.map((item) => <li key={item}>{item}</li>)}</ul>
                  </section>
                )}
                {mission.result.coverage && (
                  <section className="coverage-card">
                    <div>
                      <b>{Math.round(mission.result.coverage.ratio * 100)}%</b>
                      <span>cobertura estructural</span>
                    </div>
                    <p>
                      {mission.result.coverage.analyzed_blocks}/{mission.result.coverage.total_blocks}{" "}
                      bloques analizados · {mission.result.coverage.cited_blocks} citados ·{" "}
                      {mission.result.coverage.cited_critical_blocks}/
                      {mission.result.coverage.critical_blocks} críticos cubiertos
                    </p>
                  </section>
                )}
                {mission.result.citations.length > 0 && (
                  <section className="evidence-section">
                    <h4>Fragmentos literales y ubicación</h4>
                    {mission.result.citations.map((citation) => (
                      <details key={citation.evidence_id} className="citation-card">
                        <summary>
                          [{citation.evidence_id}] {citation.label}
                          {citation.section_path.length > 0
                            ? ` · ${citation.section_path.join(" › ")}`
                            : ""}
                          {citation.page_number ? ` · página ${citation.page_number}` : ""}
                        </summary>
                        <blockquote>{citation.quote}</blockquote>
                        <code>{citation.block_id}</code>
                      </details>
                    ))}
                  </section>
                )}
                {mission.result.verification_report && (
                  <details className="proof-card">
                    <summary>Prueba independiente y objeciones abiertas</summary>
                    <dl>
                      <dt>Estado</dt><dd>{mission.result.verification_report.status}</dd>
                      <dt>Método</dt><dd>{mission.result.verification_report.verification_method}</dd>
                      <dt>Paquete</dt><dd><code>{mission.result.verification_report.evidence_bundle_hash}</code></dd>
                      <dt>Informe</dt><dd><code>{mission.result.verification_report.report_hash}</code></dd>
                    </dl>
                    <ul>
                      {mission.result.verification_report.open_objections.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </article>
            )}
            {mission.error && <p className="error">{mission.error}</p>}
            <div className="timeline">
              {events.map((event) => (
                <span key={event.sequence}>
                  <b>{event.sequence}</b>
                  {eventLabels[event.event_type] ?? event.event_type}
                </span>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
