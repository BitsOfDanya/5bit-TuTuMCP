export interface NegotiatorTripSpec {
  origin: string;
  destination: string;
  outbound_date: string;
  return_date: string | null;
  travelers: number;
  budget: number | null;
  max_transfers: number | null;
  [key: string]: unknown;
}

export interface NegotiatorTransportSegment {
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
  [key: string]: unknown;
}

export interface NegotiatorHotel {
  name: string;
  price: number;
  rating: number | null;
  booking_url: string | null;
  [key: string]: unknown;
}

export interface NegotiatorJourney {
  id: string;
  total_price: number;
  transport_price: number;
  hotel_price: number;
  outbound: NegotiatorTransportSegment;
  inbound: NegotiatorTransportSegment;
  hotel: NegotiatorHotel | null;
}

export interface NegotiatorAlternative {
  id: string;
  kind: "single" | "combination";
  score: number;
  new_trip_spec: NegotiatorTripSpec;
  journey: NegotiatorJourney;
  [key: string]: unknown;
}

export interface NegotiationResult {
  status: "success" | "negotiation_required" | "no_options";
  trip_spec: NegotiatorTripSpec;
  journeys: NegotiatorJourney[];
  alternatives: NegotiatorAlternative[];
}

export interface TripIntent {
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string | null;
  adults: number;
  budget: number | null;
  direct_only: boolean;
  hotel_rating_min: number;
}

export interface PricePoint {
  timestamp: string;
  total_price: number;
  trip_score: number;
}

export interface BestTrip {
  total_price: number;
  transport_price: number;
  hotel_price: number;
  trip_score: number;
  useful_time_hours: number;
  transfers: number;
  hotel_rating: number;
  transport: {
    id: string;
    carriers: string[];
    departure_at: string;
    arrival_at: string;
    return_departure_at: string | null;
    return_arrival_at: string | null;
    search_results_url: string | null;
  };
  hotel: {
    id: string;
    name: string;
    checkout_url: string | null;
  } | null;
}

export interface TripTracking {
  id: string;
  intent: TripIntent;
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
    status: "COLLECTING_DATA" | "BUY_NOW" | "WAIT" | "GOOD_VALUE";
    message: string;
  };
  current_trip: BestTrip;
  history: PricePoint[];
}

export interface TrackingList {
  items: TripTracking[];
}
