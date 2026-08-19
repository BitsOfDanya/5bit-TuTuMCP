import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Hotel, Plane, RefreshCw, Sparkles, TrendingDown, XCircle } from "lucide-react";
import { FormEvent, useState } from "react";

import {
  createTracking,
  listTrackings,
  refreshTracking,
  simulateTracking,
  stopTracking,
} from "./api";
import type { TrackingList, TripIntent, TripTracking } from "./types";

const statusLabels = {
  COLLECTING_DATA: "Собираем историю",
  BUY_NOW: "Можно покупать",
  WAIT: "Лучше подождать",
  GOOD_VALUE: "Хорошая цена",
} as const;

export function App() {
  const queryClient = useQueryClient();
  const trackingsQuery = useQuery({
    queryKey: ["trackings"],
    queryFn: listTrackings,
  });
  const tracking = trackingsQuery.data?.items[0] ?? null;
  const [form, setForm] = useState<TripIntent>(() => initialIntent());

  function saveTracking(updated: TripTracking) {
    queryClient.setQueryData<TrackingList>(["trackings"], (current) => ({
      items: [
        updated,
        ...(current?.items.filter((item) => item.id !== updated.id) ?? []),
      ],
    }));
  }

  const createMutation = useMutation({
    mutationFn: createTracking,
    onSuccess: saveTracking,
  });
  const simulateMutation = useMutation({
    mutationFn: simulateTracking,
    onSuccess: saveTracking,
  });
  const refreshMutation = useMutation({
    mutationFn: refreshTracking,
    onSuccess: saveTracking,
  });
  const stopMutation = useMutation({
    mutationFn: stopTracking,
    onSuccess: saveTracking,
  });
  const error =
    createMutation.error ??
    simulateMutation.error ??
    refreshMutation.error ??
    stopMutation.error ??
    trackingsQuery.error;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createMutation.mutate(form);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a href="/" className="brand" aria-label="Smart Trip Tracker">
          <span>trip</span>
          <strong>pulse</strong>
        </a>
        <span className="mode-badge">Tutu MCP · реальный поиск</span>
      </header>

      <main>
        <section className="intro">
          <p className="eyebrow">BEST TIME TO BOOK</p>
          <h1>Когда выгоднее купить всю поездку?</h1>
          <p>
            Следим за общей стоимостью перелёта туда-обратно и отеля,
            сравнивая не только цену, но и качество комбинации.
          </p>
        </section>

        <section className="search-card" aria-labelledby="intent-title">
          <div>
            <p className="step-label">Шаг 1</p>
            <h2 id="intent-title">Опишите поездку</h2>
          </div>
          <form onSubmit={handleSubmit}>
            <label>
              Откуда
              <input
                required
                value={form.origin}
                onChange={(event) => setForm({ ...form, origin: event.target.value })}
              />
            </label>
            <label>
              Куда
              <input
                required
                value={form.destination}
                onChange={(event) =>
                  setForm({ ...form, destination: event.target.value })
                }
              />
            </label>
            <label>
              Туда
              <input
                required
                type="date"
                value={form.departure_date}
                onChange={(event) =>
                  setForm({ ...form, departure_date: event.target.value })
                }
              />
            </label>
            <label>
              Обратно
              <input
                required
                type="date"
                value={form.return_date}
                onChange={(event) =>
                  setForm({ ...form, return_date: event.target.value })
                }
              />
            </label>
            <label>
              Бюджет, ₽
              <input
                min={1}
                type="number"
                value={form.budget ?? ""}
                onChange={(event) =>
                  setForm({
                    ...form,
                    budget: event.target.value ? Number(event.target.value) : null,
                  })
                }
              />
            </label>
            <label>
              Рейтинг отеля от
              <input
                max={10}
                min={0}
                step={0.1}
                type="number"
                value={form.hotel_rating_min}
                onChange={(event) =>
                  setForm({
                    ...form,
                    hotel_rating_min: Number(event.target.value),
                  })
                }
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.direct_only}
                onChange={(event) =>
                  setForm({ ...form, direct_only: event.target.checked })
                }
              />
              Только прямые рейсы
            </label>
            <button disabled={createMutation.isPending} type="submit">
              {createMutation.isPending ? "Ищем комбинации…" : "Следить за поездкой"}
            </button>
          </form>
          {error ? (
            <p className="error" role="alert">
              {error instanceof Error ? error.message : "Произошла ошибка."}
            </p>
          ) : null}
        </section>

        {tracking ? (
          <section className="dashboard" aria-labelledby="dashboard-title">
            <div className="dashboard-heading">
              <div>
                <p className="step-label">Шаг 2</p>
                <h2 id="dashboard-title">
                  {tracking.intent.origin} → {tracking.intent.destination}
                </h2>
              </div>
              <div className="dashboard-actions">
                <button
                  className="ghost-button"
                  disabled={!tracking.active || refreshMutation.isPending}
                  type="button"
                  onClick={() => refreshMutation.mutate(tracking.id)}
                >
                  <RefreshCw size={17} aria-hidden="true" />
                  Обновить
                </button>
                <button
                  className="simulate-button"
                  disabled={!tracking.active || simulateMutation.isPending}
                  type="button"
                  onClick={() => simulateMutation.mutate(tracking.id)}
                >
                  <Sparkles size={17} aria-hidden="true" />
                  Добавить demo-точку
                </button>
                {tracking.active ? (
                  <button
                    className="stop-button"
                    disabled={stopMutation.isPending}
                    type="button"
                    onClick={() => stopMutation.mutate(tracking.id)}
                  >
                    <XCircle size={17} aria-hidden="true" />
                    {stopMutation.isPending ? "Останавливаем…" : "Остановить"}
                  </button>
                ) : (
                  <span className="inactive-badge">Отслеживание остановлено</span>
                )}
              </div>
            </div>

            <div className="metrics">
              <Metric label="Сейчас" value={money(tracking.summary.current_price)} />
              <Metric label="Минимум" value={money(tracking.summary.minimum_price)} />
              <Metric label="Средняя" value={money(tracking.summary.average_price)} />
              <Metric
                label="Trip Score"
                value={`${tracking.current_trip.trip_score} / 100`}
              />
            </div>

            <article className={`recommendation ${tracking.recommendation.status.toLowerCase()}`}>
              <TrendingDown size={24} aria-hidden="true" />
              <div>
                <strong>{statusLabels[tracking.recommendation.status]}</strong>
                <p>{tracking.recommendation.message}</p>
              </div>
            </article>

            <div className="dashboard-grid">
              <article className="chart-card">
                <h3>Стоимость лучшей поездки</h3>
                <PriceChart tracking={tracking} />
              </article>
              <article className="combination-card">
                <h3>Текущая комбинация</h3>
                <div>
                  <Plane aria-hidden="true" />
                  <span>
                    <small>Перелёт туда-обратно</small>
                    <strong>{tracking.current_trip.transport.carriers.join(", ")}</strong>
                    <b>{money(tracking.current_trip.transport_price)}</b>
                  </span>
                </div>
                <div>
                  <Hotel aria-hidden="true" />
                  <span>
                    <small>Отель</small>
                    <strong>{tracking.current_trip.hotel.name}</strong>
                    <b>{money(tracking.current_trip.hotel_price)}</b>
                  </span>
                </div>
                <dl>
                  <div><dt>Полезное время</dt><dd>{tracking.current_trip.useful_time_hours} ч</dd></div>
                  <div><dt>Пересадки</dt><dd>{tracking.current_trip.transfers}</dd></div>
                  <div><dt>Рейтинг отеля</dt><dd>{tracking.current_trip.hotel_rating}</dd></div>
                </dl>
              </article>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <article><span>{label}</span><strong>{value}</strong></article>;
}

function PriceChart({ tracking }: { tracking: TripTracking }) {
  const width = 720;
  const height = 230;
  const padding = 28;
  const prices = tracking.history.map((point) => point.total_price);
  const minimum = Math.min(...prices);
  const maximum = Math.max(...prices);
  const range = Math.max(maximum - minimum, 1);
  const x = (index: number) =>
    tracking.history.length === 1
      ? width / 2
      : padding + (index * (width - padding * 2)) / (tracking.history.length - 1);
  const y = (price: number) =>
    height - padding - ((price - minimum) / range) * (height - padding * 2);
  const points = tracking.history
    .map((point, index) => `${x(index)},${y(point.total_price)}`)
    .join(" ");

  return (
    <svg
      className="price-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="График изменения общей стоимости поездки"
    >
      <line x1={padding} x2={width - padding} y1={y(minimum)} y2={y(minimum)} />
      <polyline points={points} />
      {tracking.history.map((point, index) => (
        <circle key={point.timestamp} cx={x(index)} cy={y(point.total_price)} r="6">
          <title>
            {new Date(point.timestamp).toLocaleString("ru-RU")}: {money(point.total_price)}
          </title>
        </circle>
      ))}
    </svg>
  );
}

function initialIntent(): TripIntent {
  const departure = new Date();
  departure.setDate(departure.getDate() + 21);
  const returning = new Date(departure);
  returning.setDate(returning.getDate() + 3);
  return {
    origin: "Москва",
    destination: "Казань",
    departure_date: isoDate(departure),
    return_date: isoDate(returning),
    adults: 1,
    budget: 45_000,
    direct_only: true,
    hotel_rating_min: 8,
  };
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function money(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}
