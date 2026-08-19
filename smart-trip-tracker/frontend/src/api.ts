import type {
  NegotiationResult,
  TrackingList,
  TripTracking,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail ?? "Запрос не выполнен.");
  }
  return response.json() as Promise<T>;
}

export function listTrackings(): Promise<TrackingList> {
  return request<TrackingList>("/api/v1/trips");
}

export function createTracking(result: NegotiationResult): Promise<TripTracking> {
  return request<TripTracking>("/api/v1/trips", {
    method: "POST",
    body: JSON.stringify(result),
  });
}

export function recordNegotiation({
  id,
  result,
}: {
  id: string;
  result: NegotiationResult;
}): Promise<TripTracking> {
  return request<TripTracking>(`/api/v1/trips/${id}/observations`, {
    method: "POST",
    body: JSON.stringify(result),
  });
}

export type SimulationScenario = "drop" | "spike";

export function simulateTracking({
  id,
  scenario,
}: {
  id: string;
  scenario: SimulationScenario;
}): Promise<TripTracking> {
  return request<TripTracking>(`/api/v1/trips/${id}/simulate?scenario=${scenario}`, {
    method: "POST",
  });
}

export function refreshTracking(id: string): Promise<TripTracking> {
  return request<TripTracking>(`/api/v1/trips/${id}/refresh`, {
    method: "POST",
  });
}

export function stopTracking(id: string): Promise<TripTracking> {
  return request<TripTracking>(`/api/v1/trips/${id}`, {
    method: "DELETE",
  });
}
