import {
  ArrowLeft,
  ArrowRight,
  BellRing,
  CalendarDays,
  CircleStop,
  Clock3,
  ExternalLink,
  RefreshCw,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useEffect, useRef } from "react";

import type { SearchOption } from "../api/chat";
import type { PricePoint, TripTracking } from "../api/tracker";

const recommendationTitles = {
  COLLECTING_DATA: "Собираем историю цены",
  BUY_NOW: "Подходящий момент для покупки",
  WAIT: "Можно немного подождать",
  GOOD_VALUE: "Цена сейчас выгодная",
} as const;

interface SmartTripTrackerWidgetProps {
  option: SearchOption;
  tracking: TripTracking | null;
  error: string;
  isCreating: boolean;
  isRefreshing: boolean;
  isStopping: boolean;
  onBack: () => void;
  onRetry: () => void;
  onRefresh: () => void;
  onStop: () => void;
}

export function SmartTripTrackerWidget({
  option,
  tracking,
  error,
  isCreating,
  isRefreshing,
  isStopping,
  onBack,
  onRetry,
  onRefresh,
  onStop,
}: SmartTripTrackerWidgetProps) {
  const widgetRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const widget = widgetRef.current;
    if (!widget) {
      return;
    }
    const activeWidget: HTMLElement = widget;
    const focusableSelector =
      'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';
    activeWidget.querySelector<HTMLElement>(focusableSelector)?.focus();

    function keepFocusInside(event: KeyboardEvent) {
      if (event.key !== "Tab") {
        return;
      }
      const focusable = activeWidget.querySelectorAll<HTMLElement>(focusableSelector);
      const first = focusable.item(0);
      const last = focusable.item(focusable.length - 1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }

    activeWidget.addEventListener("keydown", keepFocusInside);
    return () => activeWidget.removeEventListener("keydown", keepFocusInside);
  }, []);

  return (
    <div className="tracker-backdrop">
      <section
        ref={widgetRef}
        className="tracker-widget"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tracker-widget-title"
      >
        <header className="tracker-header">
          <button type="button" onClick={onBack} aria-label="Вернуться к Джарвеллу">
            <ArrowLeft size={20} aria-hidden="true" />
          </button>
          <span className="tracker-logo" aria-hidden="true">
            <BellRing size={20} />
          </span>
          <div>
            <strong id="tracker-widget-title">Отслеживание цены</strong>
            <span>Smart Trip Tracker</span>
          </div>
        </header>

        {isCreating ? <TrackerLoading option={option} /> : null}
        {!isCreating && error && !tracking ? (
          <TrackerError message={error} onRetry={onRetry} />
        ) : null}
        {!isCreating && tracking ? (
          <TrackerContent
            tracking={tracking}
            error={error}
            isRefreshing={isRefreshing}
            isStopping={isStopping}
            onRefresh={onRefresh}
            onStop={onStop}
          />
        ) : null}
      </section>
    </div>
  );
}

function TrackerContent({
  tracking,
  error,
  isRefreshing,
  isStopping,
  onRefresh,
  onStop,
}: {
  tracking: TripTracking;
  error: string;
  isRefreshing: boolean;
  isStopping: boolean;
  onRefresh: () => void;
  onStop: () => void;
}) {
  const bookingUrl =
    tracking.current_trip.transport.search_results_url ??
    tracking.current_trip.hotel?.checkout_url;
  const difference = tracking.summary.difference_from_min;

  return (
    <div className="tracker-content">
      <div className="tracker-route-row">
        <div>
          <h2>
            {tracking.intent.origin}
            <ArrowRight size={20} aria-hidden="true" />
            {tracking.intent.destination}
          </h2>
          <p>
            <span>
              <CalendarDays size={15} aria-hidden="true" />
              {formatDateRange(
                tracking.intent.departure_date,
                tracking.intent.return_date,
              )}
            </span>
            <span>
              <UserRound size={15} aria-hidden="true" />
              {travelerLabel(tracking.intent.adults)}
            </span>
          </p>
        </div>
        <span className={`tracker-live-status${tracking.active ? " active" : ""}`}>
          <i aria-hidden="true" />
          {tracking.active ? "Цена отслеживается" : "Отслеживание остановлено"}
        </span>
      </div>

      <section className="tracker-summary" aria-label="Текущая стоимость поездки">
        <div className="tracker-current-price">
          <span>Текущая стоимость поездки</span>
          <strong>{money(tracking.summary.current_price)}</strong>
          <p>
            {difference > 0
              ? `На ${money(difference)} выше минимальной цены`
              : "Это минимальная цена за всё время"}
          </p>
          <small>
            <Clock3 size={13} aria-hidden="true" /> Проверено {dateTime(tracking.last_checked_at)}
          </small>
        </div>
        <article
          className={`tracker-recommendation ${tracking.recommendation.status.toLowerCase()}`}
        >
          <Sparkles size={21} aria-hidden="true" />
          <div>
            <span>Рекомендация</span>
            <strong>{recommendationTitles[tracking.recommendation.status]}</strong>
            <p>{tracking.recommendation.message}</p>
          </div>
        </article>
      </section>

      {error ? <p className="tracker-error-inline" role="alert">{error}</p> : null}

      <section className="tracker-chart-card" aria-labelledby="tracker-chart-title">
        <div className="tracker-section-heading">
          <div>
            <h3 id="tracker-chart-title">Динамика стоимости</h3>
            <p>Транспорт и проживание в одной цене</p>
          </div>
          <span><i /> Цена поездки</span>
        </div>
        <PriceChart history={tracking.history} />
      </section>

      <div className="tracker-metrics" aria-label="Сводка по цене">
        <Metric label="Минимальная" value={money(tracking.summary.minimum_price)} />
        <Metric label="Средняя" value={money(tracking.summary.average_price)} />
        <Metric label="Оценка поездки" value={`${tracking.current_trip.trip_score} / 100`} />
        <Metric label="Наблюдений" value={String(tracking.history.length)} />
      </div>

      <footer className="tracker-actions">
        <button
          className="tracker-refresh-button"
          type="button"
          disabled={!tracking.active || isRefreshing}
          onClick={onRefresh}
        >
          <RefreshCw
            className={isRefreshing ? "spinning" : undefined}
            size={17}
            aria-hidden="true"
          />
          {isRefreshing ? "Проверяем…" : "Проверить цену"}
        </button>
        {bookingUrl ? (
          <a href={bookingUrl} target="_blank" rel="noreferrer">
            К билетам <ExternalLink size={15} aria-hidden="true" />
          </a>
        ) : null}
        {tracking.active ? (
          <button
            className="tracker-stop-button"
            type="button"
            disabled={isStopping}
            onClick={onStop}
          >
            <CircleStop size={16} aria-hidden="true" />
            {isStopping ? "Останавливаем…" : "Остановить"}
          </button>
        ) : null}
      </footer>
    </div>
  );
}

function PriceChart({ history }: { history: PricePoint[] }) {
  const points = history.slice(-10);
  if (!points.length) {
    return <p className="tracker-chart-empty">История появится после первой проверки.</p>;
  }

  const width = 720;
  const height = 220;
  const plot = { left: 62, right: 20, top: 30, bottom: 34 };
  const prices = points.map((point) => point.total_price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const padding = Math.max((max - min) * 0.2, max * 0.035, 1);
  const floor = Math.max(0, min - padding);
  const ceiling = max + padding;
  const range = ceiling - floor;
  const x = (index: number) =>
    points.length === 1
      ? width / 2
      : plot.left + (index * (width - plot.left - plot.right)) / (points.length - 1);
  const y = (price: number) =>
    height - plot.bottom - ((price - floor) / range) * (height - plot.top - plot.bottom);
  const line = points.map((point, index) => `${x(index)},${y(point.total_price)}`).join(" ");
  const area = `${plot.left},${height - plot.bottom} ${line} ${x(points.length - 1)},${height - plot.bottom}`;
  const guides = [ceiling, (ceiling + floor) / 2, floor];

  return (
    <svg
      className="tracker-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="График изменения стоимости поездки"
    >
      <defs>
        <linearGradient id="tracker-chart-area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#7657e8" stopOpacity="0.24" />
          <stop offset="100%" stopColor="#7657e8" stopOpacity="0" />
        </linearGradient>
      </defs>
      {guides.map((price) => (
        <g key={price}>
          <line x1={plot.left} x2={width - plot.right} y1={y(price)} y2={y(price)} />
          <text x={plot.left - 9} y={y(price) + 4}>{shortMoney(price)}</text>
        </g>
      ))}
      <polygon points={area} />
      <polyline points={line} />
      {points.map((point, index) => (
        <circle key={`${point.timestamp}-${index}`} cx={x(index)} cy={y(point.total_price)} r="5">
          <title>{`${dateTime(point.timestamp)}: ${money(point.total_price)}`}</title>
        </circle>
      ))}
      <text className="tracker-chart-time" x={x(0)} y={height - 8}>{shortTime(points[0].timestamp)}</text>
      {points.length > 1 ? (
        <text className="tracker-chart-time" x={x(points.length - 1)} y={height - 8} textAnchor="end">
          {shortTime(points.at(-1)!.timestamp)}
        </text>
      ) : null}
    </svg>
  );
}

function TrackerLoading({ option }: { option: SearchOption }) {
  return (
    <div className="tracker-loading" role="status">
      <span><RefreshCw className="spinning" size={25} aria-hidden="true" /></span>
      <h2>{option.title}</h2>
      <p>Подключаем отслеживание и сохраняем текущую цену…</p>
    </div>
  );
}

function TrackerError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="tracker-empty-error" role="alert">
      <span><BellRing size={24} aria-hidden="true" /></span>
      <h2>Не удалось включить отслеживание</h2>
      <p>{message}</p>
      <button type="button" onClick={onRetry}>Попробовать ещё раз</button>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <article><span>{label}</span><strong>{value}</strong></article>;
}

function money(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

function shortMoney(value: number): string {
  return `${Math.round(value / 1000)} тыс.`;
}

function formatDateRange(from: string, to: string | null): string {
  const formatter = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
  const departure = formatter.format(new Date(`${from}T12:00:00`));
  return to
    ? `${departure} — ${formatter.format(new Date(`${to}T12:00:00`))}`
    : departure;
}

function dateTime(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortTime(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(
    new Date(value),
  );
}

function travelerLabel(count: number): string {
  const suffix = count % 10 === 1 && count % 100 !== 11 ? "путешественник" : "путешественника";
  return `${count} ${suffix}`;
}
