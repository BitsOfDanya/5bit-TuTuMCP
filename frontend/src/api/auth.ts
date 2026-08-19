import type { AuthSession, CodeRequested } from "../types";

interface ApiErrorPayload {
  detail?: string;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new Error(payload.detail ?? "Не удалось выполнить запрос.");
  }

  return response.json() as Promise<T>;
}

export function getSession(): Promise<AuthSession> {
  return apiRequest<AuthSession>("/api/v1/auth/me");
}

export function requestCode(login: string): Promise<CodeRequested> {
  return apiRequest<CodeRequested>("/api/v1/auth/code/request", {
    method: "POST",
    body: JSON.stringify({ login }),
  });
}

export function verifyCode(challengeId: string, code: string): Promise<AuthSession> {
  return apiRequest<AuthSession>("/api/v1/auth/code/verify", {
    method: "POST",
    body: JSON.stringify({ challenge_id: challengeId, code }),
  });
}

export function passwordAuth(email: string, password: string): Promise<AuthSession> {
  return apiRequest<AuthSession>("/api/v1/auth/password", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/api/v1/auth/logout", {
    method: "POST",
  });
}
