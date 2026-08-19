import type { TrackingPayload } from "./chat";

export type RecommendationStatus =
  | "COLLECTING_DATA"
  | "BUY_NOW"
  | "WAIT"
  | "GOOD_VALUE";

export interface PricePoint {
  timestamp: string;
  total_price: number;
  trip_score: number;
}

export interface TripTracking {
  id: string;
  intent: {
    origin: string;
    destination: string;
    departure_date: string;
    return_date: string | null;
    adults: number;
    budget: number | null;
    direct_only: boolean;
    hotel_rating_min: number;
  };
  active: boolean;
  created_at: string;
  last_checked_at: string;
  summary: {
    current_price: number;
    minimum_price: number;
    average_price: number;
    difference_from_min: number;
  };
  recommendation: {
    status: RecommendationStatus;
    message: string;
  };
  current_trip: {
    total_price: number;
    transport_price: number;
    hotel_price: number;
    trip_score: number;
    useful_time_hours: number;
    transfers: number;
    hotel_rating: number;
    transport: {
      id: string;
      price: number;
      currency: string;
      departure_at: string;
      arrival_at: string;
      return_departure_at: string | null;
      return_arrival_at: string | null;
      duration_minutes: number;
      transfers: number;
      carriers: string[];
      search_results_url: string | null;
    };
    hotel: {
      id: string;
      name: string;
      price_total: number;
      currency: string;
      rating: number;
      checkout_url: string | null;
    } | null;
  };
  history: PricePoint[];
}

async function request(path: string, init?: RequestInit): Promise<TripTracking> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail ?? "Не удалось обновить отслеживание цены.");
  }
  return response.json() as Promise<TripTracking>;
}

export function createTracking(payload: TrackingPayload): Promise<TripTracking> {
  return request("/api/v1/tracker/trips", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function refreshTracking(id: string): Promise<TripTracking> {
  return request(`/api/v1/tracker/trips/${id}/refresh`, { method: "POST" });
}

export function stopTracking(id: string): Promise<TripTracking> {
  return request(`/api/v1/tracker/trips/${id}`, { method: "DELETE" });
}
