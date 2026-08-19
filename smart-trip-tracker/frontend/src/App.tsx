import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Hotel, Plane, RefreshCw, TrendingDown, XCircle } from "lucide-react";
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
  const searchError =
    createMutation.error ??
    trackingsQuery.error;
  const actionError =
    simulateMutation.error ??
    refreshMutation.error ??
    stopMutation.error;

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
          {searchError ? (
            <p className="error" role="alert">
              {searchError instanceof Error ? searchError.message : "Произошла ошибка."}
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
            {actionError ? (
              <p className="error" role="alert">
                {actionError instanceof Error ? actionError.message : "Произошла ошибка."}
              </p>
            ) : null}

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


            <section className="scenario-panel" aria-labelledby="scenario-title">
              <div>
                <p className="step-label">Тестовый стенд</p>
                <h3 id="scenario-title">Проверить динамику и негативный сценарий</h3>
                <p>
                  Эти кнопки не вызывают MCP: они добавляют контролируемую точку
                  относительно последней цены.
                </p>
              </div>
              <div className="scenario-actions">
                <button
                  className="scenario-drop"
                  disabled={!tracking.active || simulateMutation.isPending}
                  type="button"
                  onClick={() =>
                    simulateMutation.mutate({ id: tracking.id, scenario: "drop" })
                  }
                >
                  <ArrowDownRight size={18} aria-hidden="true" />
                  Цена снизилась на 7%
                </button>
                <button
                  className="scenario-spike"
                  disabled={!tracking.active || simulateMutation.isPending}
                  type="button"
                  onClick={() =>
                    simulateMutation.mutate({ id: tracking.id, scenario: "spike" })
                  }
                >
                  <ArrowUpRight size={18} aria-hidden="true" />
                  Цена выросла на 20%
                </button>
              </div>
            </section>

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
  const height = 260;
  const plot = { left: 72, right: 20, top: 24, bottom: 42 };
  const history = tracking.history.slice(-10);
  const prices = history.map((point) => point.total_price);
  const minimum = Math.min(...prices);
  const maximum = Math.max(...prices);
  const margin = Math.max((maximum - minimum) * 0.15, maximum * 0.03, 1);
  const floor = Math.max(0, minimum - margin);
  const ceiling = maximum + margin;
  const range = ceiling - floor;
  const x = (index: number) =>
    history.length === 1
      ? width / 2
      : plot.left +
        (index * (width - plot.left - plot.right)) / (history.length - 1);
  const y = (price: number) =>
    height -
    plot.bottom -
    ((price - floor) / range) * (height - plot.top - plot.bottom);
  const points = history
    .map((point, index) => `${x(index)},${y(point.total_price)}`)
    .join(" ");
  const guides = [ceiling, (ceiling + floor) / 2, floor];
  const latest = history.at(-1)!;
  const latestIndex = history.length - 1;

  return (
    <>
      <svg
        className="price-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="График изменения общей стоимости поездки"
      >
        {guides.map((price) => (
          <g key={price}>
            <line
              x1={plot.left}
              x2={width - plot.right}
              y1={y(price)}
              y2={y(price)}
            />
            <text className="axis-label" x={plot.left - 10} y={y(price) + 4}>
              {shortMoney(price)}
            </text>
          </g>
        ))}
        <polyline points={points} />
        {history.map((point, index) => (
          <circle
            key={`${point.timestamp}-${index}`}
            cx={x(index)}
            cy={y(point.total_price)}
            r="6"
          >
            <title>
              {dateTime(point.timestamp)}: {money(point.total_price)}
            </title>
          </circle>
        ))}
        <text
          className="point-value"
          x={x(latestIndex)}
          y={Math.max(y(latest.total_price) - 13, 14)}
        >
          {money(latest.total_price)}
        </text>
        <text className="time-label" x={x(0)} y={height - 10}>
          {shortTime(history[0].timestamp)}
        </text>
        {history.length > 1 ? (
          <text
            className="time-label"
            textAnchor="end"
            x={x(latestIndex)}
            y={height - 10}
          >
            {shortTime(latest.timestamp)}
          </text>
        ) : null}
      </svg>

      <ol className="price-history" aria-label="История изменения цены">
        {history.map((point, index) => {
          const previous = history[index - 1];
          const delta = previous ? point.total_price - previous.total_price : null;
          const direction = delta === null || delta === 0 ? "same" : delta > 0 ? "up" : "down";
          return (
            <li key={`history-${point.timestamp}-${index}`}>
              <time dateTime={point.timestamp}>{dateTime(point.timestamp)}</time>
              <strong>{money(point.total_price)}</strong>
              <span className={`price-delta ${direction}`}>
                {delta === null
                  ? "Первая точка"
                  : delta === 0
                    ? "Без изменений"
                    : `${delta > 0 ? "+" : ""}${money(delta)}`}
              </span>
            </li>
          );
        })}
      </ol>
    </>
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

const moneyFormatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});
const compactMoneyFormatter = new Intl.NumberFormat("ru-RU", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const shortTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function money(value: number): string {
  return moneyFormatter.format(value);
}

function shortMoney(value: number): string {
  return `${compactMoneyFormatter.format(Math.round(value))} ₽`;
}

function dateTime(value: string): string {
  return dateTimeFormatter.format(new Date(value));
}

function shortTime(value: string): string {
  return shortTimeFormatter.format(new Date(value));
}
