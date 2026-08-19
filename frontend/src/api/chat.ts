export interface AgentChatRequest {
  user_id: string;
  session_id: string | null;
  message: string;
}

export interface SearchSegment {
  mode: string;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  price: number;
  currency: string;
  duration_minutes: number | null;
  transfers: number;
  carrier: string | null;
  voyage_no: string | null;
}

export interface SearchHotel {
  name: string;
  price: number;
  currency: string;
  stars: number | null;
  rating: number | null;
  address: string | null;
  check_in: string | null;
  check_out: string | null;
  nights: number | null;
  photo_url: string | null;
}

export interface SearchOption {
  id: string;
  kind: "journey" | "relaxation";
  title: string;
  explanation: string | null;
  total_price: number;
  currency: string;
  outbound: SearchSegment;
  inbound: SearchSegment;
  hotel: SearchHotel | null;
  changes: string[];
  action_url: string | null;
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
  tool_statuses: Record<string, string>;
  search_options: SearchOption[];
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
