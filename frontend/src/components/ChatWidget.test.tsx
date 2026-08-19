import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useState } from "react";
import { axe } from "vitest-axe";
import { beforeEach, expect, test } from "vitest";

import { server } from "../test/server";
import type { User } from "../types";
import { ChatWidget, type ChatExperience } from "./ChatWidget";

const authenticatedUser: User = {
  id: "11111111-1111-4111-8111-111111111111",
  login: "traveller@example.com",
  display_name: "Traveller",
};

beforeEach(() => {
  window.localStorage.clear();
});

function renderChat() {
  return render(<ChatWidgetHarness />);
}

function ChatWidgetHarness() {
  const [isOpen, setOpen] = useState(false);
  const [experience, setExperience] = useState<ChatExperience>("chat");
  return (
    <ChatWidget
      user={authenticatedUser}
      isOpen={isOpen}
      onOpenChange={setOpen}
      experience={experience}
      onExperienceChange={setExperience}
      onRequireAuth={() => undefined}
      onNotify={() => undefined}
    />
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

test("renders MCP search results as external booking links", async () => {
  const user = userEvent.setup();
  let trackingRequest: Record<string, unknown> | null = null;
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
            inbound: null,
            hotel: null,
            changes: [],
            action_url: "https://www.tutu.ru/poezda/view_d.php?np=002E",
          },
        ],
      }),
    ),
    http.post("/api/v1/tracker/trips", async ({ request }) => {
      trackingRequest = await request.json() as Record<string, unknown>;
      return HttpResponse.json({
        id: "44444444-4444-4444-8444-444444444444",
        intent: {
          origin: "Москва",
          destination: "Казань",
          departure_date: "2026-09-01",
          return_date: null,
          adults: 1,
          budget: null,
          direct_only: true,
          hotel_rating_min: 0,
        },
        active: true,
        created_at: "2026-08-19T10:00:00Z",
        last_checked_at: "2026-08-19T10:00:00Z",
        summary: {
          current_price: 18_900,
          minimum_price: 18_900,
          average_price: 18_900,
          difference_from_min: 0,
        },
        recommendation: {
          status: "COLLECTING_DATA",
          message: "Нужно больше наблюдений для уверенной рекомендации.",
        },
        current_trip: {
          total_price: 18_900,
          transport_price: 18_900,
          hotel_price: 0,
          trip_score: 80,
          useful_time_hours: 92.5,
          transfers: 0,
          hotel_rating: 0,
          transport: {
            id: "journey-1:transport",
            price: 18_900,
            currency: "RUB",
            departure_at: "2026-09-01T10:00:00+03:00",
            arrival_at: "2026-09-01T21:30:00+03:00",
            return_departure_at: null,
            return_arrival_at: null,
            duration_minutes: 690,
            transfers: 0,
            carriers: ["ФПК"],
            search_results_url: "https://www.tutu.ru/poezda/view_d.php?np=002E",
          },
          hotel: null,
        },
        history: [{ timestamp: "2026-08-19T10:00:00Z", total_price: 18_900, trip_score: 80 }],
      }, { status: 201 });
    }),
  );

  renderChat();
  await user.click(screen.getByRole("button", { name: "Открыть чат с Джарвеллом" }));
  await user.type(screen.getByLabelText("Сообщение Джарвеллу"), "Покажи варианты");
  await user.click(screen.getByRole("button", { name: "Отправить сообщение" }));

  const options = await screen.findByLabelText("Найденные варианты");
  const card = within(options).getByRole("article");
  const checkout = within(card).getByRole("link", {
    name: /оформить на tutu: Москва — Казань/i,
  });
  expect(within(card).getByText("18 900 ₽")).toBeInTheDocument();
  expect(card).toHaveTextContent("10:00");
  expect(card).toHaveTextContent("21:30");
  expect(card).toHaveTextContent("Оформить на Tutu");
  expect(checkout).toHaveAttribute(
    "href",
    "https://www.tutu.ru/poezda/view_d.php?np=002E",
  );
  expect(checkout).toHaveAttribute("target", "_blank");
  expect(screen.queryByText("Перейти к вариантам")).not.toBeInTheDocument();

  await user.click(within(card).getByRole("button", {
    name: "Отслеживать цену варианта Москва — Казань",
  }));
  const tracker = await screen.findByRole("dialog", { name: "Отслеживание цены" });
  expect(within(tracker).getByText("Цена отслеживается")).toBeInTheDocument();
  expect(trackingRequest).toMatchObject({
    status: "success",
    trip_spec: { origin: "Москва", destination: "Казань" },
  });
});

test("accepts a round trip and runs a non-mutating What-if simulation", async () => {
  const user = userEvent.setup();
  let savedTrips = 0;
  const outbound = {
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
    booking_url: "https://www.tutu.ru/outbound",
  };
  const inbound = {
    ...outbound,
    origin: "Казань",
    destination: "Москва",
    departure: "2026-09-05T18:00:00+03:00",
    arrival: "2026-09-06T05:30:00+03:00",
    price: 9_400,
    booking_url: "https://www.tutu.ru/inbound",
  };
  server.use(
    http.post("/api/v1/agent/chat", () =>
      HttpResponse.json({
        user_id: authenticatedUser.id,
        session_id: "44444444-4444-4444-8444-444444444444",
        response: "Нашёл вариант. Можно сохранить его для Rescue и What-if.",
        trip: {
          service_type: "train",
          origin: "Москва",
          destination: "Казань",
          start_date: "2026-09-01",
          end_date: "2026-09-05",
          preferred_time: "10:00:00",
          passengers: 1,
          budget: 30_000,
          currency: "RUB",
          is_international: null,
        },
        missing_fields: [],
        is_complete: true,
        next_action: "redirect_to_search",
        decision_intent: "search",
        redirect_url: null,
        tools_used: ["negotiate_constraints"],
        tool_statuses: { negotiate_constraints: "success" },
        search_options: [{
          id: "journey-roundtrip",
          kind: "journey",
          title: "Москва — Казань — Москва",
          explanation: "Без пересадок",
          total_price: 18_900,
          currency: "RUB",
          outbound,
          inbound,
          hotel: null,
          changes: [],
          action_url: outbound.booking_url,
          tracking_payload: null,
        }],
      }),
    ),
    http.put("/api/v1/trips/current", async ({ request }) => {
      savedTrips += 1;
      const body = await request.json() as { journey: { id: string } };
      expect(body.journey.id).toBe("journey-roundtrip");
      return HttpResponse.json({ ...body, updated_at: "2026-08-19T12:00:00Z" });
    }),
    http.post("/api/v1/trips/current/what-if", async ({ request }) => {
      expect(await request.json()).toEqual({ message: "А если вернуться до 10 утра?" });
      return HttpResponse.json({
        kind: "what_if",
        result: {
          simulation: true,
          candidates: [{
            id: "what-if-1",
            rank: 1,
            summary: { headline: "Вернуться до 10 утра", price_delta_label: "+2 100 ₽" },
            journey: {
              id: "what-if-1",
              total_price: 21_000,
              outbound,
              inbound: { ...inbound, arrival: "2026-09-06T09:10:00+03:00" },
              hotel: null,
            },
            impact: {
              price_delta: 2_100,
              savings: 0,
              outbound_departure_delta_minutes: 0,
              inbound_arrival_delta_minutes: 220,
              components_changed: ["inbound"],
              components_preserved: ["outbound"],
              disruption_count: 1,
            },
          }],
        },
      });
    }),
  );

  renderChat();
  await user.click(screen.getByRole("button", { name: "Открыть чат с Джарвеллом" }));
  await user.type(screen.getByLabelText("Сообщение Джарвеллу"), "Найди поездку туда и обратно");
  await user.click(screen.getByRole("button", { name: "Отправить сообщение" }));
  await user.click(await screen.findByRole("button", { name: "Выбрать поездку" }));
  await waitFor(() => expect(savedTrips).toBe(1));

  await user.click(screen.getByRole("tab", { name: /А что если/ }));
  await user.type(screen.getByLabelText("Какой сценарий сравнить?"), "А если вернуться до 10 утра?");
  await user.click(screen.getByRole("button", { name: "Сравнить" }));

  expect(await screen.findByText("Вернуться до 10 утра")).toBeInTheDocument();
  expect(screen.getByText(/Текущий вариант не меняю/)).toBeInTheDocument();
  expect(savedTrips).toBe(1);
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
