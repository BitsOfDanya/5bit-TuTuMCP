import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";

import { server } from "../test/server";
import { GroupPreferences } from "./GroupPreferences";

test("builds a virtual group profile and shows conflicts", async () => {
  const user = userEvent.setup();
  server.use(
    http.post("/api/v1/preferences/group/profile", async ({ request }) => {
      expect(await request.json()).toEqual({
        group_id: "Друзья",
        participant_profile_ids: ["profile-2"],
      });
      return HttpResponse.json({
        result: {
          group_id: "Друзья",
          member_count: 2,
          consensus_score: 0.72,
          highlights: ["Группа чаще выбирает прямые маршруты."],
          conflicts: [
            {
              dimension: "price",
              severity: "medium",
              description: "Одному участнику важнее цена, другому — скорость.",
            },
          ],
        },
      });
    }),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <GroupPreferences onClose={vi.fn()} />
    </QueryClientProvider>,
  );

  await user.type(screen.getByLabelText("Название группы"), "Друзья");
  await user.type(screen.getByLabelText("ID участников через запятую"), "profile-2");
  await user.click(screen.getByRole("button", { name: "Собрать групповой профиль" }));

  expect(await screen.findByText("Лучший баланс для группы")).toBeInTheDocument();
  expect(screen.getByText(/Средняя согласованность/)).toBeInTheDocument();
  expect(screen.getByText(/одному участнику важнее цена/i)).toBeInTheDocument();
});
