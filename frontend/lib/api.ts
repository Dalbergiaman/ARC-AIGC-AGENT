import type { DashboardConfig, DashboardConfigPatch, DashboardProviders } from "@/lib/types";

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
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
