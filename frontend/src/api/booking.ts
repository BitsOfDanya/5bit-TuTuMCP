import type { SearchOption } from "./chat";

export type BookingProductType = "train" | "flight" | "bus" | "hotel";

export type BookingStep =
  | "select_carriage"
  | "select_room"
  | "select_fare"
  | "select_extras"
  | "select_seats"
  | "confirm_fare"
  | "passengers"
  | "documents"
  | "guests"
  | "confirm"
  | "checkout";

export interface BookingStepOption {
  id: string;
  title: string;
  description: string;
  price_delta: number;
  available: boolean;
}

export interface Booking {
  id: string;
  user_id: string;
  session_id: string;
  product_type: BookingProductType;
  option: SearchOption;
  steps: BookingStep[];
  current_step: BookingStep;
  completed_steps: BookingStep[];
  selections: Record<string, unknown>;
  travelers_count: number;
  current_options: BookingStepOption[];
  checkout_url: string | null;
  inventory_source: "preview";
  provider_notice: string;
}

export interface BookingAssistance {
  assistant_message: string;
  proposed_data: Record<string, unknown>;
  missing_fields: string[];
  can_apply: boolean;
  requires_user_confirmation: boolean;
}

export interface ExtractedPassengerDocument {
  document_type: "international_passport" | "domestic_passport" | "birth_certificate" | "unknown";
  last_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  last_name_latin: string | null;
  first_name_latin: string | null;
  date_of_birth: string | null;
  document_series: string | null;
  document_number: string | null;
}

export interface DocumentExtractionResult {
  document: ExtractedPassengerDocument;
  missing_fields: string[];
  manual_review_required: boolean;
}

interface ApiErrorPayload {
  detail?: string;
}

export async function createBooking(request: {
  user_id: string;
  session_id: string;
  option: SearchOption;
}): Promise<Booking> {
  return bookingRequest("/api/v1/bookings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function getBooking(bookingId: string, userId: string): Promise<Booking> {
  return bookingRequest(
    `/api/v1/bookings/${encodeURIComponent(bookingId)}?user_id=${encodeURIComponent(userId)}`,
  );
}

export async function submitBookingStep(
  bookingId: string,
  request: { user_id: string; step: BookingStep; data: Record<string, unknown> },
): Promise<Booking> {
  return bookingRequest(`/api/v1/bookings/${encodeURIComponent(bookingId)}/steps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function assistBooking(
  bookingId: string,
  request: { user_id: string; instruction: string },
): Promise<BookingAssistance> {
  return apiRequest(`/api/v1/bookings/${encodeURIComponent(bookingId)}/assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function extractPassengerDocument(
  userId: string,
  sessionId: string,
  file: File,
): Promise<DocumentExtractionResult> {
  const formData = new FormData();
  formData.append("document", file);
  return apiRequest(
    `/api/v1/agent/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}/documents/extract`,
    { method: "POST", body: formData },
  );
}

async function apiRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: "include", ...init });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new Error(payload.detail ?? "Не удалось продолжить оформление.");
  }
  return response.json() as Promise<T>;
}

async function bookingRequest(url: string, init?: RequestInit): Promise<Booking> {
  return apiRequest<Booking>(url, init);
}
