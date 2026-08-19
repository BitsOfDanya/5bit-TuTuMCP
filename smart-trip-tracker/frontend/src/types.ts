export interface TripIntent {
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string;
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
    return_departure_at: string;
    return_arrival_at: string;
    search_results_url: string | null;
  };
  hotel: {
    id: string;
    name: string;
    checkout_url: string | null;
  };
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
