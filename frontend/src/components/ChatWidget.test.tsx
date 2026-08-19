import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { beforeEach, expect, test } from "vitest";

import { server } from "../test/server";
import type { User } from "../types";
import { ChatWidget } from "./ChatWidget";

const authenticatedUser: User = {
  id: "11111111-1111-4111-8111-111111111111",
  login: "traveller@example.com",
  display_name: "Traveller",
};

beforeEach(() => window.localStorage.clear());

test("opens the chat and restores focus after Escape", async () => {
  const user = userEvent.setup();
  render(<ChatWidget user={authenticatedUser} />);

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

  render(<ChatWidget user={authenticatedUser} />);
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

test("chat dialog has no automated accessibility violations", async () => {
  const user = userEvent.setup();
  const { container } = render(<ChatWidget user={authenticatedUser} />);

  await user.click(screen.getByRole("button", { name: "Открыть чат с Джарвеллом" }));
  await screen.findByText(/ваш помощник по путешествиям/i);

  const results = await axe(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
});
