import {
  ArrowRight,
  BellRing,
  BusFront,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Hotel,
  Info,
  Plane,
  RefreshCw,
  Sparkles,
  TrainFront,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { SearchOption, SearchSegment } from "../api/chat";

interface TravelOptionCardsProps {
  options: SearchOption[];
  acceptedOptionId?: string | null;
  acceptingOptionId?: string | null;
  onAccept?: (option: SearchOption) => void;
  onTrack?: (option: SearchOption) => void;
}

export function TravelOptionCards({
  options,
  acceptedOptionId = null,
  acceptingOptionId = null,
  onAccept,
  onTrack,
}: TravelOptionCardsProps) {
  if (!options.length) {
    return null;
  }

  return (
    <div className="travel-options" aria-label="Найденные варианты">
      {options.map((option) => (
        <TravelOptionCard
          key={`${option.kind}-${option.id}`}
          option={option}
          isAccepted={acceptedOptionId === option.id}
          isAccepting={acceptingOptionId === option.id}
          onAccept={onAccept}
          onTrack={onTrack}
        />
      ))}
    </div>
  );
}

function TravelOptionCard({
  option,
  isAccepted,
  isAccepting,
  onAccept,
  onTrack,
}: {
  option: SearchOption;
  isAccepted: boolean;
  isAccepting: boolean;
  onAccept?: (option: SearchOption) => void;
  onTrack?: (option: SearchOption) => void;
}) {
  const href = safeActionUrl(option.action_url);
  const canAccept = Boolean(option.outbound && option.inbound && onAccept);
  return (
    <article className={`travel-option-card${isAccepted ? " travel-option-card-accepted" : ""}`}>
      <>
      <div className="travel-option-heading">
        <span className={`travel-option-kind travel-option-kind-${option.kind}`}>
          {option.kind === "relaxation" ? (
            <>
              <Sparkles size={12} aria-hidden="true" /> Гибкий вариант
            </>
          ) : (
            "Подходит"
          )}
        </span>
        <strong>{formatMoney(option.total_price, option.currency)}</strong>
      </div>

      {option.personalized && option.rank_after === 1 ? (
        <span className="travel-option-personalized">
          <Sparkles size={12} aria-hidden="true" /> Лучше подходит вам
        </span>
      ) : null}

      <h3>{option.title}</h3>
      {option.explanation ? <p className="travel-option-explanation">{option.explanation}</p> : null}

      <div className="travel-option-segments">
        {option.outbound ? <SegmentRow label="Туда" segment={option.outbound} /> : null}
        {option.inbound ? <SegmentRow label="Обратно" segment={option.inbound} /> : null}
      </div>

      {option.hotel ? (
        <div className="travel-option-hotel">
          <Hotel size={15} aria-hidden="true" />
          <span>
            <strong>{option.hotel.name}</strong>
            {option.hotel.nights ? ` · ${formatNights(option.hotel.nights)}` : ""}
          </span>
          {option.hotel.rating ? <em>{option.hotel.rating.toFixed(1)}</em> : null}
        </div>
      ) : null}

      {option.changes.length ? (
        <div className="travel-option-changes">
          <RefreshCw size={13} aria-hidden="true" />
          <span>{option.changes.slice(0, 2).join(" · ")}</span>
        </div>
      ) : null}


      {option.preference_reasons?.length ? (
        <details className="travel-option-reasons">
          <summary><Sparkles size={13} aria-hidden="true" /> Почему этот вариант</summary>
          <div className="travel-option-preference-reasons">
            {option.preference_reasons.slice(0, 3).map((reason) => (
              <span key={reason}>{reason}</span>
            ))}
          </div>
        </details>
      ) : null}

      {option.price_intelligence ? (
        <PriceIntelligence insight={option.price_intelligence} currency={option.currency} />
      ) : null}

      <div className="travel-option-actions">
        {canAccept ? (
          <button
            type="button"
            disabled={isAccepting || isAccepted}
            onClick={() => onAccept?.(option)}
          >
            {isAccepted ? (
              <><CheckCircle2 size={14} aria-hidden="true" /> Поездка сохранена</>
            ) : isAccepting ? "Сохраняем…" : "Выбрать поездку"}
          </button>
        ) : null}
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            aria-label={`Оформить на Tutu: ${option.title}`}
          >
            Оформить на Tutu <ExternalLink size={14} aria-hidden="true" />
          </a>
        ) : (
          <span>Ссылка оформления пока недоступна</span>
        )}
        {onTrack ? (
          <button
            className="travel-option-track"
            type="button"
            disabled={!option.tracking_payload && !option.outbound}
            onClick={() => onTrack(option)}
            aria-label={`Отслеживать цену варианта ${option.title}`}
          >
            <BellRing size={14} aria-hidden="true" />
            {option.price_intelligence ? "Показать динамику" : "Проверить цену"}
          </button>
        ) : null}
      </div>
      </>
    </article>
  );
}

function PriceIntelligence({
  insight,
  currency,
}: {
  insight: NonNullable<SearchOption["price_intelligence"]>;
  currency: string;
}) {
  const title = {
    BUY_NOW: "Лучше покупать сейчас",
    GOOD_VALUE: "Хорошая цена",
    WAIT: "Можно подождать",
    COLLECTING_DATA: "Наблюдаем за ценой",
  }[insight.status];

  return (
    <aside className={`travel-price-intelligence price-${insight.status.toLowerCase()}`}>
      <div>
        <BellRing size={15} aria-hidden="true" />
        <span><strong>{title}</strong><small>{insight.message}</small></span>
      </div>
      <details>
        <summary><Info size={12} aria-hidden="true" /> Почему?</summary>
        <dl>
          <div><dt>Сейчас</dt><dd>{formatMoney(insight.current_price, currency)}</dd></div>
          <div><dt>Минимум</dt><dd>{formatMoney(insight.minimum_price, currency)}</dd></div>
          <div><dt>Средняя</dt><dd>{formatMoney(insight.average_price, currency)}</dd></div>
        </dl>
        <small>{observationLabel(insight.observations)}</small>
      </details>
    </aside>
  );
}

function SegmentRow({
  label,
  segment,
}: {
  label: string;
  segment: SearchSegment;
}) {
  const ModeIcon = modeIcon(segment.mode);
  return (
    <div className="travel-segment">
      <span className="travel-segment-icon">
        <ModeIcon size={15} aria-hidden="true" />
      </span>
      <div>
        <small>{label}</small>
        <strong>
          {formatTime(segment.departure)}
          <ArrowRight size={12} aria-hidden="true" />
          {formatTime(segment.arrival)}
        </strong>
        <span>
          {formatDate(segment.departure)} · {segment.carrier || transportLabel(segment.mode)}
          {segment.voyage_no ? ` ${segment.voyage_no}` : ""}
        </span>
      </div>
      <div className="travel-segment-meta">
        <span>
          <Clock3 size={11} aria-hidden="true" /> {formatDuration(segment)}
        </span>
        <small>{transferLabel(segment.transfers)}</small>
      </div>
    </div>
  );
}

function modeIcon(mode: string): LucideIcon {
  if (mode === "flight") {
    return Plane;
  }
  if (mode === "bus") {
    return BusFront;
  }
  return TrainFront;
}

function transportLabel(mode: string): string {
  return mode === "flight" ? "Самолёт" : mode === "bus" ? "Автобус" : "Поезд";
}

function formatTime(value: string): string {
  const match = value.match(/^\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})/);
  return match ? `${match[1]}:${match[2]}` : value;
}

function formatDate(value: string): string {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) {
    return value;
  }
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(date);
}

function formatDuration(segment: SearchSegment): string {
  const minutes = segment.duration_minutes ?? durationBetween(segment.departure, segment.arrival);
  if (minutes === null) {
    return "—";
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours} ч${rest ? ` ${rest} мин` : ""}` : `${rest} мин`;
}

function durationBetween(departure: string, arrival: string): number | null {
  const start = new Date(departure).getTime();
  const end = new Date(arrival).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) {
    return null;
  }
  return Math.round((end - start) / 60_000);
}

function transferLabel(transfers: number): string {
  if (transfers === 0) {
    return "Без пересадок";
  }
  const suffix = transfers === 1 ? "пересадка" : transfers < 5 ? "пересадки" : "пересадок";
  return `${transfers} ${suffix}`;
}

function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString("ru-RU")} ${currency}`;
  }
}

function formatNights(nights: number): string {
  const suffix = nights % 10 === 1 && nights % 100 !== 11 ? "ночь" : nights % 10 < 5 &&
    (nights % 100 < 10 || nights % 100 >= 20) ? "ночи" : "ночей";
  return `${nights} ${suffix}`;
}

function observationLabel(value: number): string {
  const suffix = value % 10 === 1 && value % 100 !== 11
    ? "наблюдение"
    : value % 10 >= 2 && value % 10 <= 4 && (value % 100 < 10 || value % 100 >= 20)
      ? "наблюдения"
      : "наблюдений";
  return `${value} ${suffix} в истории`;
}

function safeActionUrl(value: string | null): string | null {
  if (!value) {
    return null;
  }
  try {
    const url = new URL(value, window.location.origin);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }
    return value;
  } catch {
    return null;
  }
}
