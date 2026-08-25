import type {
  AgentMission,
  DocumentRecord,
  MemoryRecord,
  MissionEvent,
} from "@noosfera/contracts";

const API_URL = import.meta.env.VITE_SHEILY_API_URL ?? "http://localhost:8101";

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<string> {
  const value = await request<{ access_token: string }>("/v1/auth/login", "", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return value.access_token;
}

export async function createConversation(token: string): Promise<string> {
  const value = await request<{ id: string }>("/v1/conversations", token, {
    method: "POST",
    body: JSON.stringify({ title: "Sesión soberana" }),
  });
  return value.id;
}

export function uploadDocument(token: string, file: File): Promise<DocumentRecord> {
  const body = new FormData();
  body.append("upload", file);
  return request<DocumentRecord>("/v1/documents", token, { method: "POST", body });
}

export function sendMessage(
  token: string,
  conversationId: string,
  content: string,
  documentIds: string[],
  remember: boolean,
): Promise<AgentMission> {
  const path = `/v1/conversations/${encodeURIComponent(conversationId)}/messages`;
  return request<AgentMission>(path, token, {
    method: "POST",
    body: JSON.stringify({ content, document_ids: documentIds, remember }),
  });
}

export function getMission(token: string, missionId: string): Promise<AgentMission> {
  return request<AgentMission>(`/v1/missions/${encodeURIComponent(missionId)}`, token);
}

export function approveMission(
  token: string,
  missionId: string,
  approved: boolean,
  rememberResult: boolean,
): Promise<AgentMission> {
  const path = `/v1/missions/${encodeURIComponent(missionId)}/approval`;
  return request<AgentMission>(path, token, {
    method: "POST",
    body: JSON.stringify({
      approved,
      remember_result: rememberResult,
      reason: "Decisión de la persona propietaria",
    }),
  });
}

export function listMemories(token: string): Promise<MemoryRecord[]> {
  return request<MemoryRecord[]>("/v1/memories", token);
}

export function deleteMemory(token: string, memoryId: string): Promise<void> {
  return request<void>(`/v1/memories/${encodeURIComponent(memoryId)}`, token, {
    method: "DELETE",
  });
}

export async function streamMission(
  token: string,
  missionId: string,
  onEvent: (event: MissionEvent) => void,
): Promise<void> {
  const response = await fetch(
    `${API_URL}/v1/missions/${encodeURIComponent(missionId)}/events`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok || !response.body) throw new Error("No se pudo abrir el flujo de misión");
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += value;
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const data = block.split("\n").find((line) => line.startsWith("data: "));
      if (data) onEvent(JSON.parse(data.slice(6)) as MissionEvent);
    }
  }
}
