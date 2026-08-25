import type { AuditEntry, OperatorStatus } from "@noosfera/contracts";

const API_URL = import.meta.env.VITE_SHEILY_API_URL ?? "http://localhost:8101";

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  }
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<string> {
  const value = await request<{ access_token: string }>("/v1/auth/login", "", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return value.access_token;
}

export function loadStatus(token: string): Promise<OperatorStatus> {
  return request<OperatorStatus>("/v1/operator/status", token);
}

export function loadAudit(token: string): Promise<AuditEntry[]> {
  return request<AuditEntry[]>("/v1/operator/audit?limit=100", token);
}

export function setSafeStop(token: string, active: boolean): Promise<{ accepted: boolean }> {
  return request<{ accepted: boolean }>("/v1/operator/stop", token, {
    method: "POST",
    body: JSON.stringify({
      active,
      reason: active ? "Parada manual desde la consola operacional" : "Reanudación manual verificada",
    }),
  });
}
