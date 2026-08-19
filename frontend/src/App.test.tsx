import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { expect, test } from "vitest";

import { App } from "./App";
import { server } from "./test/server";

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

test("opens the sign-in dialog and completes passwordless authentication", async () => {
  const user = userEvent.setup();
  server.use(
    http.post("/api/v1/auth/code/request", () =>
      HttpResponse.json({
        challenge_id: "challenge-123456789",
        expires_in: 300,
        debug_code: "123456",
      }),
    ),
    http.post("/api/v1/auth/code/verify", () =>
      HttpResponse.json({
        user: {
          id: "user-1",
          login: "demo@example.com",
          display_name: "Demo",
        },
      }),
    ),
  );

  renderApp();

  await user.click(await screen.findByRole("button", { name: "Войти" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Телефон или электронная почта"), "demo@example.com");
  await user.click(screen.getByRole("button", { name: "Отправить код" }));

  expect(await screen.findByText(/код для локальной разработки: 123456/i)).toBeInTheDocument();
  await user.type(screen.getByLabelText("Код подтверждения"), "123456");
  await user.click(screen.getByRole("button", { name: "Продолжить" }));

  expect(await screen.findByRole("button", { name: /demo/i })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("registers a new account and signs the user in", async () => {
  const user = userEvent.setup();
  server.use(
    http.post("/api/v1/auth/register", async ({ request }) => {
      const body = (await request.json()) as {
        name: string;
        email: string;
        password: string;
      };
      expect(body).toEqual({
        name: "Анна Петрова",
        email: "anna@example.com",
        password: "very-safe-password",
      });
      return HttpResponse.json(
        {
          user: {
            id: "user-2",
            login: body.email,
            display_name: body.name,
          },
        },
        { status: 201 },
      );
    }),
  );

  renderApp();
  await user.click(await screen.findByRole("button", { name: "Войти" }));
  await user.click(screen.getByRole("button", { name: "Зарегистрироваться по почте" }));
  const dialog = within(screen.getByRole("dialog"));
  await user.type(dialog.getByLabelText("Имя"), "Анна Петрова");
  await user.type(dialog.getByLabelText("Электронная почта"), "anna@example.com");
  await user.type(dialog.getByLabelText("Придумайте пароль"), "very-safe-password");
  await user.type(dialog.getByLabelText("Повторите пароль"), "very-safe-password");
  await user.click(dialog.getByRole("button", { name: "Зарегистрироваться" }));

  expect(await screen.findByRole("button", { name: /анна петрова/i })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("opens Jarvell from the product list as a modal", async () => {
  const user = userEvent.setup();
  renderApp();

  await user.click(await screen.findByRole("tab", { name: "Джарвел" }));

  const dialog = screen.getByRole("dialog", { name: "Джарвелл" });
  expect(dialog).toBeInTheDocument();
  expect(dialog).toHaveAttribute("aria-modal", "true");
  await waitFor(() =>
    expect(within(dialog).getByLabelText("Сообщение Джарвеллу")).toHaveFocus(),
  );
});

test("opens Cold Start inside Jarvell from the traveller card", async () => {
  const user = userEvent.setup();
  renderApp();

  await user.click(await screen.findByRole("button", { name: "Получить" }));

  const dialog = screen.getByRole("dialog", { name: "Джарвелл" });
  expect(within(dialog).getByRole("heading", { name: "Настроим поездки под тебя" })).toBeInTheDocument();
  expect(within(dialog).getByText("4 быстрых выбора")).toBeInTheDocument();
});

test("sign-in dialog has no automated accessibility violations", async () => {
  const user = userEvent.setup();
  const { container } = renderApp();

  await user.click(await screen.findByRole("button", { name: "Войти" }));

  const results = await axe(container, {
    rules: {
      "color-contrast": { enabled: false },
    },
  });
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
});
