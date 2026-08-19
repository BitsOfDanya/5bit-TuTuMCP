import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const server = setupServer(
  http.get("/api/v1/auth/me", () => HttpResponse.json({ user: null })),
  http.get("/api/v1/trips/current", () =>
    HttpResponse.json({ detail: "Принятая поездка не найдена." }, { status: 404 }),
  ),
);
