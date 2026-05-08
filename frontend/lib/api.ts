import type {
  DashboardConfig,
  DashboardConfigPatch,
  DashboardProviders,
  SessionDetailResponse,
  SessionResponse,
  SubmitMessageResponse,
} from "@/lib/types";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
}

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const url = typeof input === "string" ? `${getApiBaseUrl()}${input}` : input;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getDashboardConfig(): Promise<DashboardConfig> {
  return requestJson<DashboardConfig>("/api/dashboard/config");
}

export function updateDashboardConfig(patch: DashboardConfigPatch): Promise<DashboardConfig> {
  return requestJson<DashboardConfig>("/api/dashboard/config", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export function getDashboardProviders(): Promise<DashboardProviders> {
  return requestJson<DashboardProviders>("/api/dashboard/providers");
}

export function createSession(): Promise<SessionResponse> {
  return requestJson<SessionResponse>("/api/sessions", {
    method: "POST",
  });
}

export function listSessions(): Promise<SessionResponse[]> {
  return requestJson<SessionResponse[]>("/api/sessions");
}

export function getSession(sessionId: string): Promise<SessionDetailResponse> {
  return requestJson<SessionDetailResponse>(`/api/sessions/${sessionId}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/sessions/${sessionId}`, {
    method: "DELETE",
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
}

export function submitChatMessage(
  sessionId: string,
  content: string,
): Promise<SubmitMessageResponse> {
  return requestJson<SubmitMessageResponse>(`/api/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
