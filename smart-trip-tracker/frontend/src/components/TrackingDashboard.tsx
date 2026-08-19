import {
  ArrowRight,
  CalendarDays,
  Check,
  CircleStop,
  Clock3,
  ExternalLink,
  Hotel,
  Plane,
  RefreshCw,
  Route,
  Sparkles,
  UserRound,
} from "lucide-react";

import { dateRange, dateTime, money, time, travelerLabel } from "../formatters";
import type { TripTracking } from "../types";
import { PriceChart } from "./PriceChart";

const statusLabels = {
  COLLECTING_DATA: "Наблюдаем за ценой",
  BUY_NOW: "Подходящий момент для покупки",
  WAIT: "Можно немного подождать",
  GOOD_VALUE: "Цена сейчас выгодная",
} as const;

interface TrackingDashboardProps {
  tracking: TripTracking;
  actionError: Error | null;
  isRefreshing: boolean;
  isRecording: boolean;
  isStopping: boolean;
  onRefresh: () => void;
  onRecord: () => void;
  onStop: () => void;
}

export function TrackingDashboard({
  tracking,
  actionError,
  isRefreshing,
  isRecording,
  isStopping,
  onRefresh,
  onRecord,
  onStop,
}: TrackingDashboardProps) {
  const bookingUrl =
    tracking.current_trip.transport.search_results_url ??
    tracking.current_trip.hotel?.checkout_url;
  const difference = tracking.summary.difference_from_min;

  return (
    <>
      <div className="page-heading">
        <p className="breadcrumb">Мои поездки · Отслеживание цены</p>
        <div className="route-heading">
          <div>
            <h1 aria-label={`${tracking.intent.origin} → ${tracking.intent.destination}`}>
              {tracking.intent.origin}
              <ArrowRight aria-hidden="true" />
              {tracking.intent.destination}
            </h1>
            <div className="trip-meta">
              <span>
                <CalendarDays size={17} aria-hidden="true" />
                {dateRange(
                  tracking.intent.departure_date,
                  tracking.intent.return_date,
                )}
              </span>
              <span>
                <UserRound size={17} aria-hidden="true" />
                {travelerLabel(tracking.intent.adults)}
              </span>
            </div>
          </div>
          <span className={`tracking-status${tracking.active ? " active" : ""}`}>
            <i aria-hidden="true" />
            {tracking.active ? "Цена отслеживается" : "Отслеживание остановлено"}
          </span>
        </div>
      </div>

      <section className="overview-card" aria-labelledby="price-title">
        <div className="price-overview">
          <span id="price-title">Текущая стоимость поездки</span>
          <strong>{money(tracking.summary.current_price)}</strong>
          <p>
            {difference > 0
              ? `На ${money(difference)} выше минимальной цены`
              : "Это минимальная цена за всё время"}
          </p>
          <div className="primary-actions">
            <button
              className="primary-button"
              disabled={!tracking.active || isRefreshing}
              type="button"
              onClick={onRefresh}
            >
              <RefreshCw
                className={isRefreshing ? "spinning" : undefined}
                size={18}
                aria-hidden="true"
              />
              {isRefreshing ? "Проверяем цену…" : "Проверить цену"}
            </button>
            {bookingUrl ? (
              <a className="secondary-button" href={bookingUrl}>
                К вариантам
                <ExternalLink size={16} aria-hidden="true" />
              </a>
            ) : null}
          </div>
          <small>Последняя проверка: {dateTime(tracking.last_checked_at)}</small>
        </div>

        <article
          className={`recommendation-card ${tracking.recommendation.status.toLowerCase()}`}
        >
          <span className="recommendation-icon">
            <Sparkles size={23} aria-hidden="true" />
          </span>
          <div>
            <span>Рекомендация</span>
            <strong>{statusLabels[tracking.recommendation.status]}</strong>
            <p>{tracking.recommendation.message}</p>
          </div>
        </article>
      </section>

      {actionError ? (
        <p className="error-message page-error" role="alert">
          {actionError.message}
        </p>
      ) : null}

      <section className="metrics-row" aria-label="Сводка по стоимости">
        <Metric label="Минимальная цена" value={money(tracking.summary.minimum_price)} />
        <Metric label="Средняя цена" value={money(tracking.summary.average_price)} />
        <Metric label="Оценка поездки" value={`${tracking.current_trip.trip_score} из 100`} />
        <Metric label="Наблюдений" value={String(tracking.history.length)} />
      </section>

      <div className="dashboard-grid">
        <section className="content-card chart-card" aria-labelledby="chart-title">
          <div className="card-heading">
            <div>
              <h2 id="chart-title">Как менялась цена</h2>
              <p>Общая стоимость транспорта и проживания</p>
            </div>
            <span className="chart-legend"><i /> Цена поездки</span>
          </div>
          <PriceChart tracking={tracking} />
        </section>

        <aside className="content-card trip-card" aria-labelledby="trip-title">
          <div className="card-heading">
            <div>
              <h2 id="trip-title">Ваша поездка</h2>
              <p>Текущий лучший вариант</p>
            </div>
          </div>
          <JourneyRow
            icon={<Plane size={19} aria-hidden="true" />}
            label="Туда"
            departure={tracking.current_trip.transport.departure_at}
            arrival={tracking.current_trip.transport.arrival_at}
            carrier={tracking.current_trip.transport.carriers.join(", ")}
          />
          {tracking.current_trip.transport.return_departure_at &&
          tracking.current_trip.transport.return_arrival_at ? (
            <JourneyRow
              icon={<Plane className="plane-return" size={19} aria-hidden="true" />}
              label="Обратно"
              departure={tracking.current_trip.transport.return_departure_at}
              arrival={tracking.current_trip.transport.return_arrival_at}
              carrier={tracking.current_trip.transport.carriers.join(", ")}
            />
          ) : null}
          {tracking.current_trip.hotel ? (
            <div className="hotel-row">
              <span className="journey-icon"><Hotel size={19} aria-hidden="true" /></span>
              <div>
                <small>Проживание</small>
                <strong>{tracking.current_trip.hotel.name}</strong>
                <span>Рейтинг {tracking.current_trip.hotel_rating}</span>
              </div>
              <b>{money(tracking.current_trip.hotel_price)}</b>
            </div>
          ) : null}
          <dl className="trip-facts">
            <div><dt><Route size={15} aria-hidden="true" />Пересадки</dt><dd>{tracking.current_trip.transfers}</dd></div>
            <div><dt><Clock3 size={15} aria-hidden="true" />Время в поездке</dt><dd>{tracking.current_trip.useful_time_hours} ч</dd></div>
            <div><dt><Check size={15} aria-hidden="true" />Транспорт</dt><dd>{money(tracking.current_trip.transport_price)}</dd></div>
          </dl>
        </aside>
      </div>

      <section className="tracking-controls" aria-label="Управление отслеживанием">
        <div>
          <strong>Управление поездкой</strong>
          <p>Можно добавить результат новой проверки или остановить наблюдение.</p>
        </div>
        <div>
          {tracking.active ? (
            <>
              <button
                className="text-button"
                disabled={isRecording}
                type="button"
                onClick={onRecord}
              >
                {isRecording ? "Добавляем точку…" : "Добавить как новую точку"}
              </button>
              <button
                className="danger-button"
                disabled={isStopping}
                type="button"
                onClick={onStop}
              >
                <CircleStop size={17} aria-hidden="true" />
                {isStopping ? "Останавливаем…" : "Остановить"}
              </button>
            </>
          ) : (
            <span className="stopped-note">Наблюдение завершено</span>
          )}
        </div>
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function JourneyRow({
  icon,
  label,
  departure,
  arrival,
  carrier,
}: {
  icon: React.ReactNode;
  label: string;
  departure: string;
  arrival: string;
  carrier: string;
}) {
  return (
    <div className="journey-row">
      <span className="journey-icon">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{time(departure)} → {time(arrival)}</strong>
        <span>{carrier}</span>
      </div>
      <time dateTime={departure}>{dateTime(departure).split(",")[0]}</time>
    </div>
  );
}
