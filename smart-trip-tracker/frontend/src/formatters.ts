const moneyFormatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});
const compactMoneyFormatter = new Intl.NumberFormat("ru-RU", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
});
const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const timeFormatter = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

export function money(value: number): string {
  return moneyFormatter.format(value);
}

export function shortMoney(value: number): string {
  return `${compactMoneyFormatter.format(Math.round(value))} ₽`;
}

export function dateTime(value: string): string {
  return dateTimeFormatter.format(new Date(value));
}

export function shortTime(value: string): string {
  return dateTimeFormatter.format(new Date(value));
}

export function time(value: string): string {
  return timeFormatter.format(new Date(value));
}

export function dateRange(from: string, to: string): string {
  return `${dateFormatter.format(new Date(`${from}T12:00:00`))} — ${dateFormatter.format(
    new Date(`${to}T12:00:00`),
  )}`;
}

export function travelerLabel(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  const noun =
    mod10 === 1 && mod100 !== 11
      ? "путешественник"
      : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
        ? "путешественника"
        : "путешественников";
  return `${count} ${noun}`;
}
