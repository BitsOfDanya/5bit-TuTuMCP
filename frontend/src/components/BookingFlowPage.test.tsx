import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { expect, test } from "vitest";

import type { Booking } from "../api/booking";
import { server } from "../test/server";
import { BookingFlowPage } from "./BookingFlowPage";

const bookingId = "33333333-3333-4333-8333-333333333333";
const userId = "11111111-1111-4111-8111-111111111111";

const flightBooking: Booking = {
  id: bookingId,
  user_id: userId,
  session_id: "22222222-2222-4222-8222-222222222222",
  product_type: "flight",
  option: {
    id: "flight-1",
    kind: "journey",
    title: "Москва — Стамбул",
    explanation: null,
    total_price: 32_000,
    currency: "RUB",
    outbound: {
      mode: "flight",
      origin: "Москва",
      destination: "Стамбул",
      departure: "2026-09-01T10:00:00+03:00",
      arrival: "2026-09-01T15:00:00+03:00",
      price: 32_000,
      currency: "RUB",
      duration_minutes: 300,
      transfers: 0,
      carrier: "Тест Авиа",
      voyage_no: "TU100",
    },
    inbound: null,
    hotel: null,
    changes: [],
    action_url: "https://avia.tutu.ru/checkout/example",
  },
  steps: ["select_fare", "select_extras", "documents", "confirm", "checkout"],
  current_step: "select_fare",
  completed_steps: [],
  selections: {},
  travelers_count: 1,
  current_options: [
    { id: "basic", title: "Эконом", description: "Ручная кладь", price_delta: 0, available: true },
    { id: "optimal", title: "Оптимум", description: "Багаж и обмен", price_delta: 3500, available: true },
  ],
  checkout_url: null,
  inventory_source: "preview",
  provider_notice: "Наличие и цена подтверждаются на Туту.",
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <BookingFlowPage bookingId={bookingId} userId={userId} onBack={() => undefined} />
    </QueryClientProvider>,
  );
}

test("renders product-specific flight steps and advances after fare selection", async () => {
  const user = userEvent.setup();
  let submitted: unknown;
  server.use(
    http.get(`/api/v1/bookings/${bookingId}`, () => HttpResponse.json(flightBooking)),
    http.post(`/api/v1/bookings/${bookingId}/steps`, async ({ request }) => {
      submitted = await request.json();
      return HttpResponse.json({
        ...flightBooking,
        current_step: "select_extras",
        completed_steps: ["select_fare"],
        current_options: [
          { id: "baggage", title: "Багаж 23 кг", description: "Одна единица", price_delta: 2500, available: true },
        ],
      });
    }),
  );

  renderPage();
  expect(await screen.findByRole("heading", { name: "Выберите тариф" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Продолжить" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: /Оптимум/ }));
  expect(screen.getByRole("button", { name: "Продолжить" })).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Продолжить" }));

  expect(await screen.findByRole("heading", { name: "Багаж и услуги" })).toBeInTheDocument();
  expect(submitted).toMatchObject({
    user_id: userId,
    step: "select_fare",
    data: { option_id: "optimal" },
  });
});

test("offers all supported passenger documents for a flight", async () => {
  server.use(
    http.get(`/api/v1/bookings/${bookingId}`, () => HttpResponse.json({
      ...flightBooking,
      current_step: "documents",
      completed_steps: ["select_fare", "select_extras"],
      current_options: [],
    })),
  );

  renderPage();
  expect(await screen.findByRole("heading", { name: "Документы пассажиров" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Загранпаспорт" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Паспорт РФ" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Свидетельство о рождении" })).toBeInTheDocument();
});

test("advances after the user explicitly accepts Jarvell fare suggestion", async () => {
  const user = userEvent.setup();
  let submitted: unknown;
  server.use(
    http.get(`/api/v1/bookings/${bookingId}`, () => HttpResponse.json(flightBooking)),
    http.post(`/api/v1/bookings/${bookingId}/assist`, () => HttpResponse.json({
      assistant_message: "Рекомендую **Эконом**: он укладывается в бюджет.",
      proposed_data: { option_id: "basic" },
      missing_fields: [],
      can_apply: true,
      requires_user_confirmation: true,
    })),
    http.post(`/api/v1/bookings/${bookingId}/steps`, async ({ request }) => {
      submitted = await request.json();
      return HttpResponse.json({
        ...flightBooking,
        current_step: "select_extras",
        completed_steps: ["select_fare"],
        current_options: [],
      });
    }),
  );

  renderPage();
  await screen.findByRole("heading", { name: "Выберите тариф" });
  await user.click(screen.getByRole("button", { name: "Помочь с этим шагом" }));
  expect(await screen.findByText(/он укладывается в бюджет/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Применить и продолжить" }));

  expect(await screen.findByRole("heading", { name: "Багаж и услуги" })).toBeInTheDocument();
  expect(submitted).toMatchObject({
    step: "select_fare",
    data: { option_id: "basic" },
  });
});

test("fills passenger fields from an extracted document", async () => {
  const user = userEvent.setup();
  server.use(
    http.get(`/api/v1/bookings/${bookingId}`, () => HttpResponse.json({
      ...flightBooking,
      current_step: "documents",
      completed_steps: ["select_fare", "select_extras"],
      current_options: [],
    })),
    http.post(
      `/api/v1/agent/users/${userId}/sessions/${flightBooking.session_id}/documents/extract`,
      () => HttpResponse.json({
        document: {
          document_type: "international_passport",
          last_name: "ИВАНОВ",
          first_name: "ИВАН",
          middle_name: null,
          last_name_latin: "IVANOV",
          first_name_latin: "IVAN",
          date_of_birth: "1990-01-02",
          document_series: "72",
          document_number: "1234567",
        },
        missing_fields: [],
        manual_review_required: false,
      }),
    ),
  );

  renderPage();
  const upload = await screen.findByLabelText("Заполнить по PNG, JPG или PDF");
  await user.upload(upload, new File(["image"], "passport.png", { type: "image/png" }));

  expect(await screen.findByDisplayValue("IVANOV IVAN")).toBeInTheDocument();
  expect(screen.getByDisplayValue("1990-01-02")).toBeInTheDocument();
  expect(screen.getByDisplayValue("721234567")).toBeInTheDocument();
  expect(screen.getByText(/Обязательно проверьте/)).toBeInTheDocument();
});

test("normalizes a localized birth date returned by Jarvell", async () => {
  const user = userEvent.setup();
  server.use(
    http.get(`/api/v1/bookings/${bookingId}`, () => HttpResponse.json({
      ...flightBooking,
      current_step: "documents",
      completed_steps: ["select_fare", "select_extras"],
      current_options: [],
    })),
    http.post(`/api/v1/bookings/${bookingId}/assist`, () => HttpResponse.json({
      assistant_message: "Заполнил данные пассажира.",
      proposed_data: {
        travelers: [{
          full_name: "Иван Иванов",
          birth_date: "02.01.1990",
          document_type: "domestic_passport",
          document_number: "4510123456",
        }],
      },
      missing_fields: [],
      can_apply: true,
      requires_user_confirmation: true,
    })),
  );

  renderPage();
  await screen.findByRole("heading", { name: "Документы пассажиров" });
  await user.click(screen.getByRole("button", { name: "Помочь с этим шагом" }));
  await user.click(await screen.findByRole("button", { name: "Подставить в форму" }));

  expect(screen.getByDisplayValue("1990-01-02")).toBeInTheDocument();
});

test("booking screen has no automated accessibility violations", async () => {
  server.use(
    http.get(`/api/v1/bookings/${bookingId}`, () => HttpResponse.json(flightBooking)),
  );
  const { container } = renderPage();
  await screen.findByRole("heading", { name: "Выберите тариф" });

  const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
  await waitFor(() => expect(results.violations.map((violation) => violation.id)).toEqual([]));
});
