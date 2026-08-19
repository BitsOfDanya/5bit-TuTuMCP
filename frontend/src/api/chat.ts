export interface AgentChatRequest {
  user_id: string;
  session_id: string | null;
  message: string;
}

export interface TripDetails {
  service_type: "train" | "flight" | "bus" | "hotel" | null;
  origin: string | null;
  destination: string | null;
  start_date: string | null;
  end_date: string | null;
  preferred_time: string | null;
  passengers: number | null;
  budget: number | null;
  currency: string;
  is_international: boolean | null;
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
  booking_url: string | null;
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
  booking_url: string | null;
}

export interface TrackingPayload {
  status: "success";
  trip_spec: {
    origin: string;
    destination: string;
    outbound_date: string;
    return_date: string;
    travelers: number;
    budget: number | null;
    max_transfers: number | null;
  };
  journeys: Array<{
    id: string;
    total_price: number;
    transport_price: number;
    hotel_price: number;
    outbound: TrackingSegment;
    inbound: TrackingSegment;
    hotel: {
      name: string;
      price: number;
      rating: number | null;
      booking_url: string | null;
    } | null;
  }>;
  alternatives: [];
}

interface TrackingSegment {
  mode: "train" | "flight" | "bus" | "suburban_train";
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  price: number;
  duration_minutes: number | null;
  transfers: number;
  carrier: string | null;
  booking_url: string | null;
}

export interface SearchOption {
  id: string;
  kind: "journey" | "relaxation";
  title: string;
  explanation: string | null;
  total_price: number;
  currency: string;
  outbound: SearchSegment | null;
  inbound: SearchSegment | null;
  hotel: SearchHotel | null;
  changes: string[];
  action_url: string | null;
  tracking_payload: TrackingPayload | null;
  personalized?: boolean;
  preference_score?: number | null;
  preference_reasons?: string[];
  rank_before?: number | null;
  rank_after?: number | null;
}

export interface AgentChatResponse {
  user_id: string;
  session_id: string;
  response: string;
  trip: TripDetails;
  missing_fields: string[];
  is_complete: boolean;
  next_action:
    | "collect_trip_details"
    | "upload_passenger_documents"
    | "redirect_to_search"
    | "decision_support";
  decision_intent:
    | "search"
    | "preferences"
    | "group_preferences"
    | "rescue"
    | "what_if";
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
