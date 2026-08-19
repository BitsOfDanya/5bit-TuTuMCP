import type { NegotiationResult } from "./types";

export function initialNegotiationJson(): string {
  const departure = new Date();
  departure.setDate(departure.getDate() + 21);
  const returning = new Date(departure);
  returning.setDate(returning.getDate() + 3);
  const departureDate = isoDate(departure);
  const returnDate = isoDate(returning);

  return JSON.stringify(
    {
      status: "success",
      trip_spec: {
        origin: "Москва",
        destination: "Казань",
        outbound_date: departureDate,
        return_date: returnDate,
        travelers: 1,
        budget: 45000,
        max_transfers: 0,
      },
      journeys: [
        {
          id: "moscow-kazan-flight-hotel",
          total_price: 34800,
          transport_price: 21400,
          hotel_price: 13400,
          outbound: {
            mode: "flight",
            origin: "Москва",
            destination: "Казань",
            departure: `${departureDate}T11:00:00+03:00`,
            arrival: `${departureDate}T12:30:00+03:00`,
            price: 10700,
            duration_minutes: 90,
            transfers: 0,
            carrier: "Аэрофлот",
            booking_url: null,
          },
          inbound: {
            mode: "flight",
            origin: "Казань",
            destination: "Москва",
            departure: `${returnDate}T20:00:00+03:00`,
            arrival: `${returnDate}T21:30:00+03:00`,
            price: 10700,
            duration_minutes: 90,
            transfers: 0,
            carrier: "Аэрофлот",
            booking_url: null,
          },
          hotel: {
            name: "Отель в центре",
            price: 13400,
            rating: 8.7,
            booking_url: null,
          },
        },
      ],
      alternatives: [],
    },
    null,
    2,
  );
}

export function parseNegotiationResult(raw: string): NegotiationResult {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      throw new Error();
    }
    return parsed as NegotiationResult;
  } catch {
    throw new Error("Введите корректные данные поездки.");
  }
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}
