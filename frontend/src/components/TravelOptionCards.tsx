import {
  ArrowRight,
  BellRing,
  BusFront,
  Clock3,
  ExternalLink,
  Hotel,
  Plane,
  RefreshCw,
  Sparkles,
  TrainFront,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { SearchOption, SearchSegment } from "../api/chat";

interface TravelOptionCardsProps {
  options: SearchOption[];
  onTrack: (option: SearchOption) => void;
}

export function TravelOptionCards({ options, onTrack }: TravelOptionCardsProps) {
  if (!options.length) {
    return null;
  }

  return (
    <div className="travel-options" aria-label="Найденные варианты">
      {options.map((option) => (
        <TravelOptionCard
          key={`${option.kind}-${option.id}`}
          option={option}
          onTrack={onTrack}
        />
      ))}
    </div>
  );
}

function TravelOptionCard({
  option,
  onTrack,
}: {
  option: SearchOption;
  onTrack: (option: SearchOption) => void;
}) {
  const href = safeActionUrl(option.action_url);
  const isExternal = href?.startsWith("http://") || href?.startsWith("https://");

  return (
    <article className="travel-option-card">
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

      <div className="travel-option-actions">
        {href ? (
          <a
            className="travel-option-action"
            href={href}
            target={isExternal ? "_blank" : undefined}
            rel={isExternal ? "noreferrer" : undefined}
          >
            Перейти к оформлению
            <ExternalLink size={14} aria-hidden="true" />
          </a>
        ) : (
          <span className="travel-option-action travel-option-action-disabled">
            Ссылка недоступна
          </span>
        )}
        <button
          className="travel-option-track"
          type="button"
          disabled={!option.tracking_payload && !option.outbound}
          onClick={() => onTrack(option)}
          aria-label={`Отслеживать цену варианта ${option.title}`}
        >
          <BellRing size={14} aria-hidden="true" />
          Отслеживать цену
        </button>
      </div>
    </article>
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
