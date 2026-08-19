import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ExternalLink,
  Hotel,
  Plane,
  ShieldCheck,
  Sparkles,
  TrainFront,
  Upload,
} from "lucide-react";
import { FormEvent, lazy, Suspense, useState } from "react";

import type {
  Booking,
  BookingAssistance,
  BookingStep,
  ExtractedPassengerDocument,
} from "../api/booking";
import {
  assistBooking,
  extractPassengerDocument,
  getBooking,
  submitBookingStep,
} from "../api/booking";

interface BookingFlowPageProps {
  bookingId: string;
  userId: string;
  onBack: () => void;
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

interface TravelerDraft {
  full_name: string;
  birth_date: string;
  document_type: "international_passport" | "domestic_passport" | "birth_certificate";
  document_number: string;
}

const ChatMarkdown = lazy(() =>
  import("./ChatMarkdown").then((module) => ({ default: module.ChatMarkdown })),
);

export function BookingFlowPage({ bookingId, userId, onBack }: BookingFlowPageProps) {
  const queryClient = useQueryClient();
  const bookingQuery = useQuery({
    queryKey: ["booking", bookingId, userId],
    queryFn: () => getBooking(bookingId, userId),
  });
  const mutation = useMutation({
    mutationFn: ({ step, data }: { step: BookingStep; data: Record<string, unknown> }) =>
      submitBookingStep(bookingId, { user_id: userId, step, data }),
    onSuccess: (booking) => {
      queryClient.setQueryData(["booking", bookingId, userId], booking);
      document.documentElement.scrollTop = 0;
    },
  });

  if (bookingQuery.isPending) {
    return <main className="booking-loading">Загружаю оформление…</main>;
  }
  if (bookingQuery.isError || !bookingQuery.data) {
    return (
      <main className="booking-loading" role="alert">
        <p>{bookingQuery.error?.message ?? "Оформление не найдено."}</p>
        <button type="button" onClick={onBack}>Вернуться к поиску</button>
      </main>
    );
  }

  const booking = bookingQuery.data;
  return (
    <div className="booking-page">
      <header className="booking-header">
        <button type="button" onClick={onBack} aria-label="Вернуться к поиску">
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <strong className="booking-brand">tutu</strong>
        <span>{productLabel(booking)}</span>
      </header>

      <nav className="booking-progress" aria-label="Этапы оформления">
        {booking.steps.map((step, index) => {
          const complete = booking.completed_steps.includes(step);
          const current = booking.current_step === step;
          return (
            <span className={complete ? "complete" : current ? "current" : ""} key={`${step}-${index}`}>
              <i>{complete ? <Check size={13} /> : index + 1}</i>
              {STEP_LABELS[step]}
            </span>
          );
        })}
      </nav>

      <main className="booking-layout">
        <section className="booking-content">
          <TripSummary booking={booking} />
          <BookingStepPanel
            key={booking.current_step}
            booking={booking}
            pending={mutation.isPending}
            error={mutation.error?.message ?? ""}
            onSubmit={(data) => mutation.mutate({ step: booking.current_step, data })}
          />
        </section>
        <aside className="booking-sidebar">
          <small>Стоимость варианта</small>
          <strong>{formatMoney(booking.option.total_price, booking.option.currency)}</strong>
          <span>за {booking.travelers_count} {travelerLabel(booking)}</span>
          <hr />
          <p><ShieldCheck size={17} /> Оплата проходит на защищённой стороне Туту</p>
          <p className="booking-provider-note">{booking.provider_notice}</p>
        </aside>
      </main>
    </div>
  );
}

function TripSummary({ booking }: { booking: Booking }) {
  const Icon = booking.product_type === "hotel" ? Hotel : booking.product_type === "flight" ? Plane : TrainFront;
  return (
    <article className="booking-trip-summary">
      <span><Icon size={22} aria-hidden="true" /></span>
      <div>
        <h1>{booking.option.title}</h1>
        {booking.option.outbound ? (
          <p>{formatDateTime(booking.option.outbound.departure)} · {booking.option.outbound.carrier ?? "Туту"}</p>
        ) : (
          <p>{booking.option.hotel?.nights ?? 1} ночи · {booking.travelers_count} гостя</p>
        )}
      </div>
    </article>
  );
}

export function BookingStepPanel({
  booking,
  pending,
  error,
  onSubmit,
}: {
  booking: Booking;
  pending: boolean;
  error: string;
  onSubmit: (data: Record<string, unknown>) => void;
}) {
  const [singleOption, setSingleOption] = useState("");
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [travelerDrafts, setTravelerDrafts] = useState<TravelerDraft[]>(() =>
    Array.from({ length: booking.travelers_count }, () => emptyTravelerDraft()),
  );
  const [documentStatus, setDocumentStatus] = useState<Record<number, string>>({});
  const step = booking.current_step;

  function submitTravelers(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const travelers = travelerDrafts.map((traveler) => ({
      full_name: traveler.full_name,
      ...(step === "guests" ? {} : {
        birth_date: traveler.birth_date,
        document_type: traveler.document_type,
        document_number: traveler.document_number,
      }),
    }));
    onSubmit({ travelers });
  }

  function updateTraveler(index: number, patch: Partial<TravelerDraft>) {
    setTravelerDrafts((current) => current.map((traveler, travelerIndex) =>
      travelerIndex === index ? { ...traveler, ...patch } : traveler,
    ));
  }

  function applyAssistance(assistance: BookingAssistance) {
    const optionId = assistance.proposed_data.option_id;
    const optionIds = assistance.proposed_data.option_ids;
    const seatIds = assistance.proposed_data.seat_ids;
    const travelers = assistance.proposed_data.travelers;
    if (typeof optionId === "string") {
      setSingleOption(optionId);
    }
    if (Array.isArray(optionIds)) {
      setSelectedOptions(optionIds.filter((item): item is string => typeof item === "string"));
    }
    if (Array.isArray(seatIds)) {
      setSelectedOptions(seatIds.filter((item): item is string => typeof item === "string"));
    }
    if (Array.isArray(travelers)) {
      setTravelerDrafts((current) => current.map((traveler, index) => {
        const proposal = travelers[index];
        if (!proposal || typeof proposal !== "object") {
          return traveler;
        }
        return mergeTravelerDraft(traveler, proposal as Record<string, unknown>);
      }));
      return;
    }
    onSubmit(assistance.proposed_data);
  }

  async function handleDocumentUpload(index: number, file: File) {
    setDocumentStatus((current) => ({ ...current, [index]: "Распознаю документ…" }));
    try {
      const result = await extractPassengerDocument(booking.user_id, booking.session_id, file);
      updateTraveler(index, travelerFromDocument(result.document));
      setDocumentStatus((current) => ({
        ...current,
        [index]: result.manual_review_required
          ? "Данные заполнены — проверьте отмеченные поля."
          : "Данные заполнены. Обязательно проверьте их перед продолжением.",
      }));
    } catch (uploadError) {
      setDocumentStatus((current) => ({
        ...current,
        [index]: uploadError instanceof Error ? uploadError.message : "Не удалось распознать документ.",
      }));
    }
  }

  if (step === "checkout") {
    return (
      <section className="booking-step-card booking-checkout">
        <ShieldCheck size={40} aria-hidden="true" />
        <h2>{booking.checkout_url ? "Всё готово к оплате" : "Создать ссылку на оплату"}</h2>
        <p>Туту ещё раз проверит наличие, итоговую цену и выбранные параметры.</p>
        {booking.checkout_url ? (
          <a href={booking.checkout_url} target="_blank" rel="noreferrer">
            Перейти на Туту для оплаты <ExternalLink size={17} />
          </a>
        ) : (
          <button type="button" disabled={pending} onClick={() => onSubmit({})}>
            {pending ? "Создаю ссылку…" : "Создать checkout deeplink"}
          </button>
        )}
        {error ? <p role="alert" className="booking-error">{error}</p> : null}
      </section>
    );
  }

  if (["passengers", "documents", "guests"].includes(step)) {
    return (
      <form className="booking-step-card" onSubmit={submitTravelers}>
        <StepHeading step={step} />
        <CopilotPanel booking={booking} onApply={applyAssistance} />
        <div className="traveler-forms">
          {Array.from({ length: booking.travelers_count }, (_, index) => (
            <fieldset key={index}>
              <legend>{step === "guests" ? "Гость" : "Пассажир"} {index + 1}</legend>
              {step === "documents" ? (
                <label className="booking-document-upload">
                  <Upload size={18} aria-hidden="true" />
                  <span>Заполнить по PNG, JPG или PDF</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,application/pdf"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void handleDocumentUpload(index, file);
                    }}
                  />
                </label>
              ) : null}
              {documentStatus[index] ? <p className="booking-document-status" role="status">{documentStatus[index]}</p> : null}
              <label>Имя и фамилия
                <input
                  name={`full_name_${index}`}
                  required
                  value={travelerDrafts[index].full_name}
                  onChange={(event) => updateTraveler(index, { full_name: event.target.value })}
                />
              </label>
              {step !== "guests" ? (
                <>
                  <label>Дата рождения
                    <input
                      name={`birth_date_${index}`}
                      type="date"
                      required
                      value={travelerDrafts[index].birth_date}
                      onChange={(event) => updateTraveler(index, { birth_date: event.target.value })}
                    />
                  </label>
                  <label>Документ
                    <select
                      name={`document_type_${index}`}
                      value={travelerDrafts[index].document_type}
                      onChange={(event) => updateTraveler(index, {
                        document_type: event.target.value as TravelerDraft["document_type"],
                      })}
                    >
                      {step === "documents" ? (
                        <option value="international_passport">Загранпаспорт</option>
                      ) : null}
                      <option value="domestic_passport">Паспорт РФ</option>
                      <option value="birth_certificate">Свидетельство о рождении</option>
                    </select>
                  </label>
                  <label>Номер документа
                    <input
                      name={`document_number_${index}`}
                      required
                      value={travelerDrafts[index].document_number}
                      onChange={(event) => updateTraveler(index, { document_number: event.target.value })}
                    />
                  </label>
                </>
              ) : null}
            </fieldset>
          ))}
        </div>
        <StepFooter pending={pending} error={error} />
      </form>
    );
  }

  if (step === "confirm" || step === "confirm_fare") {
    return (
      <section className="booking-step-card">
        <StepHeading step={step} />
        <CopilotPanel booking={booking} onApply={applyAssistance} />
        <div className="booking-confirmation">
          <ShieldCheck size={30} />
          <p>{step === "confirm_fare" ? "Тариф и условия возврата проверены." : "Маршрут, услуги и данные путешественников проверены."}</p>
        </div>
        <StepFooter
          pending={pending}
          error={error}
          label={step === "confirm" ? "Подтвердить оформление" : "Подтвердить тариф"}
          onClick={() => onSubmit(step === "confirm" ? { approved: true } : { accepted: true })}
        />
      </section>
    );
  }

  const isMulti = step === "select_extras" || step === "select_seats";
  return (
    <section className="booking-step-card">
      <StepHeading step={step} />
      <CopilotPanel booking={booking} onApply={applyAssistance} />
      <div className={step === "select_seats" ? "booking-seat-grid" : "booking-option-grid"}>
        {booking.current_options.map((option) => {
          const selected = isMulti ? selectedOptions.includes(option.id) : singleOption === option.id;
          return (
            <button
              type="button"
              key={option.id}
              disabled={!option.available}
              className={selected ? "selected" : ""}
              aria-pressed={selected}
              onClick={() => {
                if (isMulti) {
                  setSelectedOptions((current) => current.includes(option.id)
                    ? current.filter((id) => id !== option.id)
                    : [...current, option.id]);
                } else {
                  setSingleOption(option.id);
                }
              }}
            >
              {step === "select_seats" ? option.id : (
                <><strong>{option.title}</strong><span>{option.description}</span>{option.price_delta ? <small>+{formatMoney(option.price_delta, booking.option.currency)}</small> : null}</>
              )}
            </button>
          );
        })}
      </div>
      {step === "select_seats" ? <p className="booking-preview-note">Места предварительные — Туту подтвердит их перед оплатой.</p> : null}
      <StepFooter
        pending={pending}
        error={error}
        disabled={step === "select_seats"
          ? selectedOptions.length !== booking.travelers_count
          : step === "select_extras"
            ? false
            : !singleOption}
        onClick={() => onSubmit(
          step === "select_extras"
            ? { option_ids: selectedOptions }
            : step === "select_seats"
              ? { seat_ids: selectedOptions }
              : { option_id: singleOption },
        )}
      />
    </section>
  );
}

function CopilotPanel({
  booking,
  onApply,
}: {
  booking: Booking;
  onApply: (assistance: BookingAssistance) => void;
}) {
  const [instruction, setInstruction] = useState("");
  const mutation = useMutation({
    mutationFn: () => assistBooking(booking.id, { user_id: booking.user_id, instruction }),
  });
  const assistance = mutation.data;

  return (
    <aside className="booking-copilot" aria-label="Помощник Джарвелл">
      <header><span><Sparkles size={18} aria-hidden="true" /></span><div><strong>Джарвелл поможет с шагом</strong><small>Предложит или заполнит — решение остаётся за вами</small></div></header>
      <label>
        <span>Пожелание или данные для заполнения</span>
        <textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="Например: выбери вариант с возвратом или заполни данные Иван Иванов…"
          rows={2}
        />
      </label>
      <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        <Sparkles size={16} aria-hidden="true" />
        {mutation.isPending ? "Думаю…" : "Помочь с этим шагом"}
      </button>
      {mutation.isError ? <p className="booking-error" role="alert">{mutation.error.message}</p> : null}
      {assistance ? (
        <div className="booking-copilot-answer" role="status">
          <Suspense fallback={<p>Готовлю ответ…</p>}>
            <ChatMarkdown content={assistance.assistant_message} />
          </Suspense>
          {assistance.missing_fields.length ? (
            <small>Нужно уточнить: {assistance.missing_fields.join(", ")}</small>
          ) : null}
          {assistance.can_apply ? (
            <button type="button" onClick={() => onApply(assistance)}>
              {isTravelerStep(booking.current_step) ? "Подставить в форму" : "Применить и продолжить"}
            </button>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}

function isTravelerStep(step: BookingStep): boolean {
  return step === "passengers" || step === "documents" || step === "guests";
}

function emptyTravelerDraft(): TravelerDraft {
  return {
    full_name: "",
    birth_date: "",
    document_type: "domestic_passport",
    document_number: "",
  };
}

function mergeTravelerDraft(
  current: TravelerDraft,
  proposal: Record<string, unknown>,
): TravelerDraft {
  const next = { ...current };
  if (typeof proposal.full_name === "string") next.full_name = proposal.full_name;
  if (typeof proposal.birth_date === "string") {
    next.birth_date = normalizeBirthDate(proposal.birth_date);
  }
  if (typeof proposal.document_number === "string") next.document_number = proposal.document_number;
  if (
    proposal.document_type === "international_passport" ||
    proposal.document_type === "domestic_passport" ||
    proposal.document_type === "birth_certificate"
  ) {
    next.document_type = proposal.document_type;
  }
  return next;
}

function normalizeBirthDate(value: string): string {
  const normalized = value.trim();
  const iso = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const localized = normalized.match(/^(\d{2})[./](\d{2})[./](\d{4})$/);
  const parts = iso
    ? { year: iso[1], month: iso[2], day: iso[3] }
    : localized
      ? { year: localized[3], month: localized[2], day: localized[1] }
      : null;
  if (!parts) {
    return "";
  }
  const date = new Date(Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day)));
  if (
    date.getUTCFullYear() !== Number(parts.year) ||
    date.getUTCMonth() !== Number(parts.month) - 1 ||
    date.getUTCDate() !== Number(parts.day)
  ) {
    return "";
  }
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function travelerFromDocument(document: ExtractedPassengerDocument): Partial<TravelerDraft> {
  const usesLatin = document.document_type === "international_passport";
  const lastName = usesLatin ? document.last_name_latin ?? document.last_name : document.last_name;
  const firstName = usesLatin ? document.first_name_latin ?? document.first_name : document.first_name;
  const fullName = [lastName, firstName, document.middle_name].filter(Boolean).join(" ");
  const documentNumber = [document.document_series, document.document_number].filter(Boolean).join("");
  return {
    ...(fullName ? { full_name: fullName } : {}),
    ...(document.date_of_birth ? { birth_date: document.date_of_birth } : {}),
    ...(document.document_type !== "unknown" ? { document_type: document.document_type } : {}),
    ...(documentNumber ? { document_number: documentNumber } : {}),
  };
}

function StepHeading({ step }: { step: BookingStep }) {
  const copy: Record<BookingStep, [string, string]> = {
    select_carriage: ["Выберите вагон", "Категория влияет на комфорт и итоговую стоимость"],
    select_room: ["Выберите номер", "Проверьте размещение и состав гостей"],
    select_fare: ["Выберите тариф", "Сравните багаж, обмен и возврат"],
    select_extras: ["Багаж и услуги", "Можно продолжить без дополнительных услуг"],
    select_seats: ["Выберите места", "По одному месту на каждого путешественника"],
    confirm_fare: ["Подтвердите тариф", "Условия будут повторно проверены на Туту"],
    passengers: ["Проверьте пассажиров", "Данные должны совпадать с документами"],
    documents: ["Документы пассажиров", "Выберите документ, подходящий для вашего маршрута"],
    guests: ["Данные гостей", "Укажите всех гостей бронирования"],
    confirm: ["Проверьте заказ", "После подтверждения создадим ссылку на оплату"],
    checkout: ["Оплата", ""],
  };
  return <header className="booking-step-heading"><h2>{copy[step][0]}</h2><p>{copy[step][1]}</p></header>;
}

function StepFooter({ pending, error, disabled, label = "Продолжить", onClick }: {
  pending: boolean;
  error: string;
  disabled?: boolean;
  label?: string;
  onClick?: () => void;
}) {
  return (
    <footer className="booking-step-footer">
      {error ? <p role="alert" className="booking-error">{error}</p> : <span />}
      <button type={onClick ? "button" : "submit"} disabled={pending || disabled} onClick={onClick}>
        {pending ? "Сохраняю…" : label} <ArrowRight size={17} />
      </button>
    </footer>
  );
}

function productLabel(booking: Booking): string {
  return { train: "Ж/д билеты", flight: "Авиабилеты", bus: "Автобусы", hotel: "Отели" }[booking.product_type];
}

function travelerLabel(booking: Booking): string {
  return booking.product_type === "hotel" ? "гостей" : "пассажиров";
}

function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

function formatDateTime(value: string): string {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) {
    return value;
  }
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  const formattedDate = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(date);
  return `${formattedDate}, ${match[4]}:${match[5]}`;
}
