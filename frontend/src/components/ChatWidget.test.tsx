import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { beforeEach, expect, test } from "vitest";

import { server } from "../test/server";
import type { Booking } from "../api/booking";
import type { User } from "../types";
import { ChatWidget } from "./ChatWidget";

const authenticatedUser: User = {
  id: "11111111-1111-4111-8111-111111111111",
  login: "traveller@example.com",
  display_name: "Traveller",
};

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState({}, "", "/");
});

function renderChat() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatWidget user={authenticatedUser} />
    </QueryClientProvider>,
  );
}

test("opens the chat and restores focus after Escape", async () => {
  const user = userEvent.setup();
  renderChat();

  const launcher = screen.getByRole("button", { name: "Открыть чат с Джарвеллом" });
  await user.click(launcher);

  const dialog = screen.getByRole("dialog", { name: "Джарвелл" });
  expect(dialog).toBeInTheDocument();
  await waitFor(() =>
    expect(within(dialog).getByLabelText("Сообщение Джарвеллу")).toHaveFocus(),
  );

  await user.keyboard("{Escape}");

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await waitFor(() => expect(launcher).toHaveFocus());
});

test("renders Markdown responses and continues the backend session", async () => {
  const user = userEvent.setup();
  const requests: Array<Record<string, unknown>> = [];
  server.use(
    http.post("/api/v1/agent/chat", async ({ request }) => {
      requests.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({
        user_id: authenticatedUser.id,
        session_id: "22222222-2222-4222-8222-222222222222",
        response: "Записал **поезд**.\n\n- Москва\n- Казань",
        trip: {},
        missing_fields: ["start_date"],
        is_complete: false,
        next_action: "collect_trip_details",
        redirect_url: null,
        tools_used: ["extract_trip_details"],
        tool_statuses: {},
      });
    }),
  );

  renderChat();
  await user.click(screen.getByRole("button", { name: "Открыть чат с Джарвеллом" }));

  const composer = screen.getByLabelText("Сообщение Джарвеллу");
  await user.type(composer, "Хочу поезд из Москвы в Казань");
  await user.click(screen.getByRole("button", { name: "Отправить сообщение" }));

  expect(await screen.findByText("поезд", { selector: "strong" })).toBeInTheDocument();
  expect(screen.getByRole("list")).toBeInTheDocument();

  await user.type(composer, "Еду 10 сентября");
  await user.click(screen.getByRole("button", { name: "Отправить сообщение" }));
  await waitFor(() => expect(requests).toHaveLength(2));

  expect(requests[0]).toMatchObject({
    user_id: authenticatedUser.id,
    session_id: null,
    message: "Хочу поезд из Москвы в Казань",
  });
  expect(requests[1]).toMatchObject({
    user_id: authenticatedUser.id,
    session_id: "22222222-2222-4222-8222-222222222222",
    message: "Еду 10 сентября",
  });
});

test("renders MCP search results as clickable inline cards", async () => {
  const user = userEvent.setup();
  const booking: Booking = {
    id: "44444444-4444-4444-8444-444444444444",
    user_id: authenticatedUser.id,
    session_id: "33333333-3333-4333-8333-333333333333",
    product_type: "train",
    option: {
      id: "journey-1",
      kind: "journey",
      title: "Москва — Казань",
      explanation: null,
      total_price: 18_900,
      currency: "RUB",
      outbound: {
        mode: "train",
        origin: "Москва",
        destination: "Казань",
        departure: "2026-09-01T10:00:00+03:00",
        arrival: "2026-09-01T21:30:00+03:00",
        price: 9_500,
        currency: "RUB",
        duration_minutes: 690,
        transfers: 0,
        carrier: "ФПК",
        voyage_no: "002Э",
      },
      inbound: null,
      hotel: null,
      changes: [],
      action_url: "https://www.tutu.ru/poezda/view_d.php?np=002E",
    },
    steps: ["select_carriage", "select_seats", "confirm_fare", "passengers", "confirm", "checkout"],
    current_step: "select_carriage",
    completed_steps: [],
    selections: {},
    travelers_count: 1,
    current_options: [
      { id: "platzkart", title: "Плацкарт", description: "27 мест", price_delta: 0, available: true },
      { id: "coupe", title: "Купе", description: "119 мест", price_delta: 1_594, available: true },
    ],
    checkout_url: null,
    inventory_source: "preview",
    provider_notice: "Наличие и цена подтверждаются на Туту.",
  };
  server.use(
    http.post("/api/v1/agent/chat", () =>
      HttpResponse.json({
        user_id: authenticatedUser.id,
        session_id: "33333333-3333-4333-8333-333333333333",
        response: "Нашёл **подходящий вариант**.",
        trip: {},
        missing_fields: [],
        is_complete: true,
        next_action: "redirect_to_search",
        redirect_url: "/search/train?origin=Москва",
        tools_used: ["negotiate_constraints"],
        tool_statuses: { negotiate_constraints: "success" },
        search_options: [
          {
            id: "journey-1",
            kind: "journey",
            title: "Москва — Казань",
            explanation: null,
            total_price: 18_900,
            currency: "RUB",
            outbound: {
              mode: "train",
              origin: "Москва",
              destination: "Казань",
              departure: "2026-09-01T10:00:00+03:00",
              arrival: "2026-09-01T21:30:00+03:00",
              price: 9_500,
              currency: "RUB",
              duration_minutes: 690,
              transfers: 0,
              carrier: "ФПК",
              voyage_no: "002Э",
            },
            inbound: {
              mode: "train",
              origin: "Казань",
              destination: "Москва",
              departure: "2026-09-05T18:00:00+03:00",
              arrival: "2026-09-06T05:30:00+03:00",
              price: 9_400,
              currency: "RUB",
              duration_minutes: 690,
              transfers: 0,
              carrier: "ФПК",
              voyage_no: "001Г",
            },
            hotel: null,
            changes: [],
            action_url: "https://www.tutu.ru/poezda/view_d.php?np=002E",
          },
        ],
      }),
    ),
    http.post("/api/v1/bookings", () => HttpResponse.json(booking)),
  );

  renderChat();
  await user.click(screen.getByRole("button", { name: "Открыть чат с Джарвеллом" }));
  await user.type(screen.getByLabelText("Сообщение Джарвеллу"), "Покажи варианты");
  await user.click(screen.getByRole("button", { name: "Отправить сообщение" }));

  const card = await screen.findByRole("button", {
    name: /выбрать вариант: Москва — Казань/i,
  });
  expect(within(card).getByText("18 900 ₽")).toBeInTheDocument();
  expect(card).toHaveTextContent("10:00");
  expect(card).toHaveTextContent("21:30");
  expect(within(card).getAllByText("Без пересадок")).toHaveLength(2);
  expect(screen.queryByText("Перейти к вариантам")).not.toBeInTheDocument();

  await user.click(card);

  expect(await screen.findByRole("heading", { name: "Выберите вагон" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Оформление поездки в чате" })).toBeInTheDocument();
  expect(screen.getByText(/шаг 1 из 6/i)).toBeInTheDocument();
  expect(window.location.pathname).toBe("/");
});

test("chat dialog has no automated accessibility violations", async () => {
  const user = userEvent.setup();
  const { container } = renderChat();

  await user.click(screen.getByRole("button", { name: "Открыть чат с Джарвеллом" }));
  await screen.findByText(/ваш помощник по путешествиям/i);

  const results = await axe(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
});
