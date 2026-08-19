import { apiRequest } from "./auth";
import type { SearchOption, SearchSegment, TripDetails } from "./chat";

export interface DecisionResult {
  kind: "rescue" | "what_if";
  result: {
    status?: string;
    simulation?: boolean;
    candidates?: DecisionCandidate[];
    reasons?: string[];
    updated_trip?: Record<string, unknown>;
  };
}

export interface AcceptedItinerary {
  trip: Record<string, unknown>;
  journey: DecisionCandidate["journey"];
  updated_at: string;
}

export interface DecisionCandidate {
  id: string;
  rank?: number;
  summary?: { headline?: string; explanation?: string; price_delta_label?: string };
  explanation?: {
    headline?: string;
    summary?: string;
    reasons?: Array<{ type: string; text: string; positive: boolean }>;
    tradeoffs?: Array<{ type: string; text: string; positive: boolean }>;
  };
  journey: {
    id: string;
    total_price: number;
    outbound: SearchSegment;
    inbound: SearchSegment;
    hotel?: SearchOption["hotel"];
  };
  exact?: boolean;
  replaced_components?: string[];
  preserved_components?: string[];
  impact?: {
    price_delta: number;
    savings: number;
    price_change_percent?: number | null;
    outbound_departure_delta_minutes: number;
    inbound_arrival_delta_minutes: number;
    components_changed: string[];
    components_preserved: string[];
    disruption_count: number;
  };
  personalization?: { reasons?: string[]; rank_before?: number; rank_after?: number } | null;
  insights?: Array<{ title: string; description: string; severity: string }>;
  relaxations?: Array<{ title: string; description: string }>;
}

export function getCurrentItinerary(): Promise<AcceptedItinerary> {
  return apiRequest("/api/v1/trips/current");
}

export async function acceptSearchOption(
  trip: TripDetails,
  option: SearchOption,
): Promise<void> {
  if (!option.outbound || !option.inbound || !trip.origin || !trip.destination) {
    throw new Error("Для Trip Rescue нужен вариант с дорогой туда и обратно.");
  }
  await apiRequest("/api/v1/trips/current", {
    method: "PUT",
    body: JSON.stringify({
      trip: {
        origin: trip.origin,
        destination: trip.destination,
        outbound_date: trip.start_date ?? option.outbound.departure.slice(0, 10),
        return_date: trip.end_date ?? option.inbound.arrival.slice(0, 10),
        outbound_after: trip.preferred_time,
        return_before: null,
        travelers: trip.passengers ?? 1,
        budget: trip.budget,
        preferred_transport: trip.service_type ? [trip.service_type] : [],
        excluded_transport: [],
        max_transfers: null,
        hard_constraints: trip.budget ? ["budget"] : [],
      },
      journey: {
        id: option.id,
        total_price: option.total_price,
        outbound: option.outbound,
        inbound: option.inbound,
        hotel: option.hotel,
      },
    }),
  });
}

export function canAcceptSearchOption(option: SearchOption): boolean {
  return Boolean(option.outbound && option.inbound);
}

export function rescueTrip(message: string): Promise<DecisionResult> {
  return apiRequest("/api/v1/trips/current/rescue", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function simulateTrip(message: string): Promise<DecisionResult> {
  return apiRequest("/api/v1/trips/current/what-if", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function applyRescueCandidate(
  result: DecisionResult,
  candidate: DecisionCandidate,
): Promise<void> {
  if (result.kind !== "rescue" || !result.result.updated_trip) {
    throw new Error("Этот результат нельзя применить к поездке.");
  }
  await apiRequest("/api/v1/trips/current", {
    method: "PUT",
    body: JSON.stringify({
      trip: result.result.updated_trip,
      journey: candidate.journey,
    }),
  });
}
