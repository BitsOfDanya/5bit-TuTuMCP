import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { test } from "vitest";

import { App } from "./App";
import { server } from "./test/server";
import type { TripTracking } from "./types";

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

const tracking: TripTracking = {
  id: "11111111-1111-1111-1111-111111111111",
  intent: {
    origin: "Москва",
    destination: "Казань",
    departure_date: "2026-09-10",
    return_date: "2026-09-13",
    adults: 1,
    budget: 45000,
    direct_only: true,
    hotel_rating_min: 8,
  },
  active: true,
  created_at: "2026-08-19T10:00:00Z",
  last_checked_at: "2026-08-19T10:00:00Z",
  summary: {
    current_price: 34800,
    minimum_price: 34800,
    average_price: 34800,
    difference_from_min: 0,
  },
  recommendation: {
    status: "COLLECTING_DATA",
    message: "Нужно ещё одно наблюдение, чтобы сравнить цену.",
  },
  current_trip: {
    total_price: 34800,
    transport_price: 21400,
    hotel_price: 13400,
    trip_score: 91,
    useful_time_hours: 56,
    transfers: 0,
    hotel_rating: 8.7,
    transport: {
      id: "flight",
      carriers: ["Demo Air"],
      departure_at: "2026-09-10T11:00:00Z",
      arrival_at: "2026-09-10T13:00:00Z",
      return_departure_at: "2026-09-13T21:00:00Z",
      return_arrival_at: "2026-09-13T23:00:00Z",
      search_results_url: null,
    },
    hotel: {
      id: "hotel",
      name: "Комфорт у набережной",
      checkout_url: null,
    },
  },
  history: [
    {
      timestamp: "2026-08-19T10:00:00Z",
      total_price: 34800,
      trip_score: 91,
    },
  ],
};

const spikedTracking: TripTracking = {
  ...tracking,
  last_checked_at: "2026-08-19T16:00:00Z",
  summary: {
    current_price: 41760,
    minimum_price: 34800,
    average_price: 38280,
    difference_from_min: 6960,
  },
  recommendation: {
    status: "WAIT",
    message: "Цена заметно выше недавнего минимума — можно подождать.",
  },
  current_trip: {
    ...tracking.current_trip,
    total_price: 41760,
    transport_price: 25680,
    hotel_price: 16080,
  },
  history: [
    ...tracking.history,
    {
      timestamp: "2026-08-19T16:00:00Z",
      total_price: 41760,
      trip_score: 91,
    },
  ],
};

test("creates tracking and shows the complete-trip dashboard", async () => {
  server.use(
    http.post("/api/v1/trips", () => HttpResponse.json(tracking, { status: 201 })),
    http.post("/api/v1/trips/:id/simulate", ({ request }) => {
      const scenario = new URL(request.url).searchParams.get("scenario");
      return HttpResponse.json(
        scenario === "spike" ? spikedTracking : tracking,
      );
    }),
    http.delete("/api/v1/trips/:id", () =>
      HttpResponse.json({ ...tracking, active: false }),
    ),
  );
  const user = userEvent.setup();
  renderApp();

  await user.click(await screen.findByRole("button", { name: "Следить за поездкой" }));

  expect(await screen.findByRole("heading", { name: "Москва → Казань" })).toBeInTheDocument();
  expect(screen.getByText("Комфорт у набережной")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /график изменения/i })).toBeInTheDocument();
  expect(screen.getByText("Собираем историю")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "История изменения цены" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Цена выросла на 20%" }));

  expect(await screen.findByText("Лучше подождать")).toBeInTheDocument();
  expect(screen.getByText(/\+6\s*960/)).toBeInTheDocument();


  await user.click(screen.getByRole("button", { name: "Остановить" }));

  expect(await screen.findByText("Отслеживание остановлено")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Обновить" })).toBeDisabled();
});


test("shows a visible error when Tutu MCP is unavailable", async () => {
  server.use(
    http.post("/api/v1/trips", () =>
      HttpResponse.json(
        { detail: "Tutu MCP is unavailable." },
        { status: 502 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderApp();

  await user.click(await screen.findByRole("button", { name: "Следить за поездкой" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Tutu MCP is unavailable.");
});
