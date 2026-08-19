import { useMutation } from "@tanstack/react-query";
import { Check, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Booking, BookingStep } from "../api/booking";
import { submitBookingStep } from "../api/booking";
import { BookingStepPanel } from "./BookingFlowPage";

interface InlineBookingFlowProps {
  initialBooking: Booking;
}

const STEP_LABELS: Record<BookingStep, string> = {
  select_carriage: "Вагон",
  select_room: "Номер",
  select_fare: "Тариф",
  select_extras: "Услуги",
  select_seats: "Места",
  confirm_fare: "Тариф",
  passengers: "Пассажиры",
  documents: "Документы",
  guests: "Гости",
  confirm: "Проверка",
  checkout: "Оплата",
};

export function InlineBookingFlow({ initialBooking }: InlineBookingFlowProps) {
  const [booking, setBooking] = useState(initialBooking);
  const rootRef = useRef<HTMLElement>(null);
  const mutation = useMutation({
    mutationFn: ({ step, data }: { step: BookingStep; data: Record<string, unknown> }) =>
      submitBookingStep(booking.id, { user_id: booking.user_id, step, data }),
    onSuccess: setBooking,
  });
  const completedCount = booking.completed_steps.length;

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      rootRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [booking.current_step]);

  return (
    <section ref={rootRef} className="chat-booking-flow" aria-label="Оформление поездки в чате">
      <header className="chat-booking-title">
        <span aria-hidden="true"><Sparkles size={17} /></span>
        <div>
          <strong>Оформляем внутри чата</strong>
          <small>{productLabel(booking)} · шаг {Math.min(completedCount + 1, booking.steps.length)} из {booking.steps.length}</small>
        </div>
        <b>{formatMoney(booking.option.total_price, booking.option.currency)}</b>
      </header>

      <div className="chat-booking-progress" aria-label="Этапы оформления">
        {booking.steps.map((step, index) => {
          const complete = booking.completed_steps.includes(step);
          const current = booking.current_step === step;
          return (
            <span
              className={complete ? "complete" : current ? "current" : ""}
              key={`${step}-${index}`}
              aria-current={current ? "step" : undefined}
            >
              <i>{complete ? <Check size={11} aria-hidden="true" /> : index + 1}</i>
              {STEP_LABELS[step]}
            </span>
          );
        })}
      </div>

      <div className="chat-booking-summary">
        <div>
          <strong>{booking.option.title}</strong>
          <small>{booking.travelers_count} {travelerLabel(booking)}</small>
        </div>
        <p><ShieldCheck size={14} aria-hidden="true" /> Финальная проверка и оплата — на защищённой стороне Туту</p>
      </div>

      <BookingStepPanel
        key={booking.current_step}
        booking={booking}
        pending={mutation.isPending}
        error={mutation.error?.message ?? ""}
        onSubmit={(data) => mutation.mutate({ step: booking.current_step, data })}
      />
    </section>
  );
}

function productLabel(booking: Booking): string {
  return { train: "Ж/д", flight: "Авиа", bus: "Автобус", hotel: "Отель" }[booking.product_type];
}

function travelerLabel(booking: Booking): string {
  const count = booking.travelers_count;
  if (booking.product_type === "hotel") {
    return count === 1 ? "гость" : count < 5 ? "гостя" : "гостей";
  }
  return count === 1 ? "пассажир" : count < 5 ? "пассажира" : "пассажиров";
}

function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}
