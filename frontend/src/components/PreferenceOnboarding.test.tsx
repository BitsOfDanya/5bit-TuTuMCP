import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";

import { PreferenceOnboarding } from "./PreferenceOnboarding";
import { server } from "../test/server";

function renderOnboarding() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onCompleted = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <PreferenceOnboarding
        isAuthenticated
        onClose={vi.fn()}
        onCompleted={onCompleted}
        onRequireAuth={vi.fn()}
      />
    </QueryClientProvider>,
  );
  return { onCompleted };
}

test("completes four cold-start choices without exposing profile_id", async () => {
  const user = userEvent.setup();
  let submittedBody: unknown;
  const questions = Array.from({ length: 4 }, (_, index) => ({
    id: `q-${index}`,
    prompt: `Выбор номер ${index + 1}`,
    left: {
      id: `q-${index}:left`,
      title: "Дешевле",
      subtitle: "Автобус",
      total_price: 4900,
      duration_minutes: 720,
      transfers: 0,
      transport: "bus",
      hotel_rating: null,
    },
    right: {
      id: `q-${index}:right`,
      title: "Быстрее",
      subtitle: "Самолёт",
      total_price: 10500,
      duration_minutes: 110,
      transfers: 0,
      transport: "flight",
      hotel_rating: null,
    },
    targets: ["price", "duration"],
  }));
  server.use(
    http.get("/api/v1/preferences/me", () => HttpResponse.json({ profile: null })),
    http.get("/api/v1/preferences/cold-start/questions", () =>
      HttpResponse.json({ total: 4, minimum_choices: 4, questions }),
    ),
    http.post("/api/v1/preferences/cold-start/complete", async ({ request }) => {
      submittedBody = await request.json();
      return HttpResponse.json({
        profile: {
          profile_id: "user-1",
          interactions: 4,
          cold_start_completed: true,
          cold_start_answers: 4,
          cold_start_confidence: 0.8,
        },
        cold_start: { questions_answered: 4, completed: true, confidence: 0.8 },
        learned_signals: [],
      });
    }),
  );

  const { onCompleted } = renderOnboarding();
  expect(screen.getByRole("heading", { name: "Настроим поездки под тебя" })).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "Начать" }));

  for (let index = 0; index < 4; index += 1) {
    await user.click(await screen.findByRole("button", { name: /Дешевле: Автобус/i }));
  }

  expect(await screen.findByText("Профиль готов")).toBeInTheDocument();
  expect(submittedBody).toEqual({
    choices: questions.map((question) => ({
      question_id: question.id,
      selected_option_id: question.left.id,
    })),
    replace: false,
  });
  expect(onCompleted).toHaveBeenCalledOnce();
});
