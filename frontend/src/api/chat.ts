export interface AgentChatRequest {
  user_id: string;
  session_id: string | null;
  message: string;
}

export interface AgentChatResponse {
  user_id: string;
  session_id: string;
  response: string;
  trip: Record<string, unknown>;
  missing_fields: string[];
  is_complete: boolean;
  next_action:
    | "collect_trip_details"
    | "upload_passenger_documents"
    | "redirect_to_search";
  redirect_url: string | null;
  tools_used: string[];
}

interface ApiErrorPayload {
  detail?: string;
}

export async function sendChatMessage(
  request: AgentChatRequest,
  signal?: AbortSignal,
): Promise<AgentChatResponse> {
  const response = await fetch("/api/v1/agent/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new Error(payload.detail ?? "Джарвелл сейчас не отвечает. Попробуйте ещё раз.");
  }

  return response.json() as Promise<AgentChatResponse>;
}
