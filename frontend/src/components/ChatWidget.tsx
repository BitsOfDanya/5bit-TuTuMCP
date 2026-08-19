import {
  ArrowUpRight,
  Check,
  ChevronDown,
  FlaskConical,
  RefreshCw,
  SendHorizontal,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import {
  FormEvent,
  KeyboardEvent,
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
} from "react";

import { sendChatMessage } from "../api/chat";
import type { SearchOption, TripDetails } from "../api/chat";
import {
  acceptSearchOption,
  applyRescueCandidate,
  getCurrentItinerary,
  rescueTrip,
  simulateTrip,
} from "../api/trips";
import type { DecisionCandidate, DecisionResult } from "../api/trips";
import type { User } from "../types";
import { TravelOptionCards } from "./TravelOptionCards";

const ChatMarkdown = lazy(() =>
  import("./ChatMarkdown").then((module) => ({ default: module.ChatMarkdown })),
);
const PreferenceOnboarding = lazy(() =>
  import("./PreferenceOnboarding").then((module) => ({
    default: module.PreferenceOnboarding,
  })),
);
const GroupPreferences = lazy(() =>
  import("./GroupPreferences").then((module) => ({
    default: module.GroupPreferences,
  })),
);

export type ChatExperience = "chat" | "preferences" | "group";
type DecisionMode = "rescue" | "what_if";

const GUEST_USER_KEY = "tutumcp.chat.guest-user-id.v1";
const INITIAL_MESSAGE = [
  "Привет! Я **Джарвелл**, ваш помощник по путешествиям.",
  "",
  "Расскажите, куда и когда хотите поехать — я уточню детали и найду варианты.",
].join("\n");

const QUICK_PROMPTS = ["Найти поезд", "Подобрать перелёт", "Настроить предпочтения"];

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  redirectUrl?: string | null;
  options?: SearchOption[];
  trip?: TripDetails;
}

interface ChatWidgetProps {
  user: User | null;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  experience: ChatExperience;
  onExperienceChange: (experience: ChatExperience) => void;
  onRequireAuth: () => void;
  onNotify: (message: string) => void;
}

export function ChatWidget({
  user,
  isOpen,
  onOpenChange,
  experience,
  onExperienceChange,
  onRequireAuth,
  onNotify,
}: ChatWidgetProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [createGreeting()]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isSending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [failedMessage, setFailedMessage] = useState("");
  const [guestUserId] = useState(getOrCreateGuestUserId);
  const [currentTrip, setCurrentTrip] = useState<TripDetails | null>(null);
  const [latestOptions, setLatestOptions] = useState<SearchOption[]>([]);
  const [acceptedOptionId, setAcceptedOptionId] = useState<string | null>(null);
  const [acceptingOptionId, setAcceptingOptionId] = useState<string | null>(null);
  const [groupCandidates, setGroupCandidates] = useState<SearchOption[]>([]);
  const [decisionMode, setDecisionMode] = useState<DecisionMode>("rescue");
  const [decisionDraft, setDecisionDraft] = useState("");
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [decisionError, setDecisionError] = useState("");
  const [isDecisionRunning, setDecisionRunning] = useState(false);
  const latestOptionsRef = useRef<SearchOption[]>([]);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const userId = user?.id ?? guestUserId;

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  useEffect(() => {
    if (!isOpen || !user) {
      return;
    }
    let active = true;
    void getCurrentItinerary()
      .then((itinerary) => {
        if (active) {
          setAcceptedOptionId(itinerary.journey.id);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [isOpen, user]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    document.body.style.overflow = "hidden";
    if (experience === "chat") {
      window.requestAnimationFrame(() => textareaRef.current?.focus());
    }

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        closeChat();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) {
        return;
      }
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
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

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [experience, isOpen, onOpenChange]);

  useEffect(() => {
    if (isOpen && experience === "chat") {
      messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [decisionResult, experience, isDecisionRunning, isOpen, isSending, messages]);

  function openChat() {
    onExperienceChange("chat");
    onOpenChange(true);
  }

  function closeChat() {
    onOpenChange(false);
    window.requestAnimationFrame(() => previousFocusRef.current?.focus());
  }

  async function submitMessage(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || isSending) {
      return;
    }
    setMessages((current) => [...current, { id: createUuid(), role: "user", content: message }]);
    setDraft("");
    setError("");
    setFailedMessage("");
    setSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await sendChatMessage(
        { user_id: userId, session_id: sessionId, message },
        controller.signal,
      );
      setSessionId(response.session_id);
      setCurrentTrip(response.trip);
      const options = response.search_options ?? [];
      if (options.length) {
        setLatestOptions(options);
        latestOptionsRef.current = options;
      }
      setMessages((current) => [
        ...current,
        {
          id: createUuid(),
          role: "assistant",
          content: response.response,
          redirectUrl: response.redirect_url,
          options,
          trip: response.trip,
        },
      ]);

      const intent = response.decision_intent ?? "search";
      if (intent === "preferences") {
        onExperienceChange("preferences");
      } else if (intent === "group_preferences") {
        setGroupCandidates(options.length ? options : latestOptionsRef.current);
        onExperienceChange("group");
      } else if (intent === "rescue" || intent === "what_if") {
        if (!user) {
          onRequireAuth();
        } else {
          await runDecision(intent, message);
        }
      }
    } catch (requestError) {
      if (controller.signal.aborted) {
        return;
      }
      setFailedMessage(message);
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Джарвелл сейчас не отвечает. Попробуйте ещё раз.",
      );
    } finally {
      if (!controller.signal.aborted) {
        setSending(false);
      }
      abortControllerRef.current = null;
    }
  }

  async function acceptOption(option: SearchOption) {
    if (!user) {
      onRequireAuth();
      return;
    }
    if (!currentTrip) {
      onNotify("Сначала завершите описание поездки в диалоге.");
      return;
    }
    setAcceptingOptionId(option.id);
    try {
      await acceptSearchOption(currentTrip, option);
      setAcceptedOptionId(option.id);
      setDecisionMode("rescue");
      onNotify("Поездка сохранена. Preference Learning учёл ваш выбор.");
    } catch (requestError) {
      onNotify(requestError instanceof Error ? requestError.message : "Не удалось сохранить поездку.");
    } finally {
      setAcceptingOptionId(null);
    }
  }

  async function runDecision(mode: DecisionMode, rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || isDecisionRunning) {
      return;
    }
    if (!user) {
      onRequireAuth();
      return;
    }
    onExperienceChange("chat");
    setDecisionMode(mode);
    setDecisionDraft("");
    setDecisionError("");
    setDecisionRunning(true);
    try {
      const result = mode === "rescue" ? await rescueTrip(message) : await simulateTrip(message);
      setDecisionResult(result);
    } catch (requestError) {
      setDecisionResult(null);
      setDecisionError(
        requestError instanceof Error ? requestError.message : "Decision Intelligence недоступен.",
      );
    } finally {
      setDecisionRunning(false);
    }
  }

  async function applyCandidate(candidate: DecisionCandidate) {
    if (!decisionResult) {
      return;
    }
    try {
      await applyRescueCandidate(decisionResult, candidate);
      onNotify("Изменение применено. Остальные части поездки сохранены.");
      setDecisionResult(null);
      setAcceptedOptionId(candidate.id);
    } catch (requestError) {
      setDecisionError(
        requestError instanceof Error ? requestError.message : "Не удалось применить изменение.",
      );
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(draft);
  }

  function handleDecisionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runDecision(decisionMode, decisionDraft);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  const showDecisionWorkspace = Boolean(
    acceptedOptionId || decisionResult || decisionError || isDecisionRunning,
  );

  return (
    <>
      <button
        className={`chat-launcher${isOpen ? " chat-launcher-hidden" : ""}`}
        type="button"
        aria-label="Открыть чат с Джарвеллом"
        aria-expanded={isOpen}
        aria-controls="jarvell-chat-dialog"
        aria-hidden={isOpen}
        tabIndex={isOpen ? -1 : 0}
        onClick={openChat}
      >
        <span className="chat-launcher-icon" aria-hidden="true"><Sparkles size={23} /></span>
        <span className="chat-launcher-copy">
          <small>Помощник в поездке</small>
          <strong>Спросить Джарвелла</strong>
        </span>
      </button>

      {isOpen ? (
        <div
          className="chat-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) {
              closeChat();
            }
          }}
        >
          <section
            ref={dialogRef}
            id="jarvell-chat-dialog"
            className="chat-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="jarvell-chat-title"
            aria-describedby="jarvell-chat-description"
          >
            <header className="chat-header">
              <span className="jarvell-avatar" aria-hidden="true"><Sparkles size={21} /></span>
              <div>
                <h2 id="jarvell-chat-title">Джарвелл</h2>
                <p id="jarvell-chat-description"><span aria-hidden="true" /> На связи · AI-помощник tutu</p>
              </div>
              <button type="button" aria-label="Закрыть чат" onClick={closeChat}>
                <X size={20} aria-hidden="true" />
              </button>
            </header>

            {experience === "preferences" ? (
              <div className="chat-experience">
                <Suspense fallback={<p role="status">Загружаем быстрые выборы…</p>}>
                  <PreferenceOnboarding
                    embedded
                    isAuthenticated={Boolean(user)}
                    onClose={() => onExperienceChange("chat")}
                    onCompleted={onNotify}
                    onRequireAuth={onRequireAuth}
                  />
                </Suspense>
              </div>
            ) : null}

            {experience === "group" ? (
              <div className="chat-experience">
                <Suspense fallback={<p role="status">Собираем групповую поездку…</p>}>
                  <GroupPreferences
                    embedded
                    candidates={groupCandidates.length ? groupCandidates : latestOptions}
                    onClose={() => onExperienceChange("chat")}
                  />
                </Suspense>
              </div>
            ) : null}

            {experience === "chat" ? (
              <>
                <div className="chat-messages" aria-live="polite" aria-busy={isSending}>
                  <p className="chat-date-marker">Сегодня</p>
                  {messages.map((message) => (
                    <article
                      className={`chat-message chat-message-${message.role}${message.options?.length ? " chat-message-has-options" : ""}`}
                      key={message.id}
                    >
                      {message.role === "assistant" ? <span className="message-avatar" aria-hidden="true">J</span> : null}
                      <div className="chat-bubble">
                        <Suspense fallback={<span>Загружаю сообщение…</span>}>
                          <ChatMarkdown content={message.content} />
                        </Suspense>
                        {message.role === "assistant" && message.options?.length && message.trip ? (
                          <ConstraintSummary trip={message.trip} />
                        ) : null}
                        <TravelOptionCards
                          options={message.options ?? []}
                          acceptedOptionId={acceptedOptionId}
                          acceptingOptionId={acceptingOptionId}
                          onAccept={(option) => void acceptOption(option)}
                        />
                        {message.options?.length && (message.trip?.passengers ?? 0) > 1 ? (
                          <div className="group-inline-prompt">
                            <Users size={16} aria-hidden="true" />
                            <span>Учитывать предпочтения всей компании?</span>
                            <button
                              type="button"
                              onClick={() => {
                                setGroupCandidates(message.options ?? []);
                                onExperienceChange("group");
                              }}
                            >
                              Создать группу
                            </button>
                          </div>
                        ) : null}
                        {message.redirectUrl && !message.options?.length ? (
                          <a className="chat-redirect" href={message.redirectUrl}>
                            Перейти к вариантам <ArrowUpRight size={15} aria-hidden="true" />
                          </a>
                        ) : null}
                      </div>
                    </article>
                  ))}

                  {messages.length === 1 ? (
                    <div className="chat-quick-prompts" aria-label="Быстрые запросы">
                      {QUICK_PROMPTS.map((prompt) => (
                        <button
                          type="button"
                          key={prompt}
                          disabled={isSending}
                          onClick={() => {
                            if (prompt === "Настроить предпочтения") {
                              onExperienceChange("preferences");
                            } else {
                              void submitMessage(prompt);
                            }
                          }}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {showDecisionWorkspace ? (
                    <DecisionWorkspace
                      mode={decisionMode}
                      draft={decisionDraft}
                      result={decisionResult}
                      error={decisionError}
                      isRunning={isDecisionRunning}
                      onModeChange={setDecisionMode}
                      onDraftChange={setDecisionDraft}
                      onSubmit={handleDecisionSubmit}
                      onApply={(candidate) => void applyCandidate(candidate)}
                    />
                  ) : null}

                  {isSending ? (
                    <div className="chat-typing" role="status" aria-label="Джарвелл печатает">
                      <span /><span /><span />
                    </div>
                  ) : null}
                  {error ? (
                    <div className="chat-error" role="alert">
                      <span>{error}</span>
                      <button type="button" onClick={() => void submitMessage(failedMessage)}>Повторить</button>
                    </div>
                  ) : null}
                  <div ref={messagesEndRef} />
                </div>

                {acceptedOptionId ? (
                  <div className="chat-whatif-actions" aria-label="Быстрые симуляции">
                    <button type="button" onClick={() => void runDecision("what_if", "А если дешевле?")}>А если дешевле?</button>
                    <button type="button" onClick={() => void runDecision("what_if", "А если вернуться раньше?")}>А если раньше?</button>
                    <button type="button" onClick={() => void runDecision("what_if", "А если без пересадок?")}>Без пересадок</button>
                  </div>
                ) : null}

                <form className="chat-composer" onSubmit={handleSubmit}>
                  <label className="visually-hidden" htmlFor="jarvell-message">Сообщение Джарвеллу</label>
                  <textarea
                    ref={textareaRef}
                    id="jarvell-message"
                    rows={1}
                    maxLength={20_000}
                    placeholder="Напишите, куда хотите поехать…"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                  />
                  <button type="submit" aria-label="Отправить сообщение" disabled={isSending || !draft.trim()}>
                    <SendHorizontal size={19} aria-hidden="true" />
                  </button>
                  <p>Enter — отправить · Shift + Enter — новая строка</p>
                </form>
              </>
            ) : null}
          </section>
        </div>
      ) : null}
    </>
  );
}

function ConstraintSummary({ trip }: { trip: TripDetails }) {
  if (!trip.destination || !trip.start_date) {
    return null;
  }
  return (
    <section className="constraint-summary" aria-label="Распознанные условия поездки">
      <small>Понял поездку</small>
      <strong>{trip.origin ? `${trip.origin} → ` : ""}{trip.destination}</strong>
      <span>{formatDate(trip.start_date)} · {trip.passengers ?? 1} пассажира</span>
      <div>
        {trip.budget ? <em>желательно до {formatMoney(trip.budget)}</em> : null}
        {trip.preferred_time ? <em>после {trip.preferred_time.slice(0, 5)}</em> : <em>время любое</em>}
      </div>
    </section>
  );
}

interface DecisionWorkspaceProps {
  mode: DecisionMode;
  draft: string;
  result: DecisionResult | null;
  error: string;
  isRunning: boolean;
  onModeChange: (mode: DecisionMode) => void;
  onDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onApply: (candidate: DecisionCandidate) => void;
}

function DecisionWorkspace({
  mode,
  draft,
  result,
  error,
  isRunning,
  onModeChange,
  onDraftChange,
  onSubmit,
  onApply,
}: DecisionWorkspaceProps) {
  return (
    <section className="decision-workspace" aria-label="Изменение принятой поездки">
      <header>
        <div><Sparkles size={17} aria-hidden="true" /><strong>Decision Intelligence</strong></div>
        <span>Текущая поездка сохранена</span>
      </header>
      <div className="decision-tabs" role="tablist" aria-label="Режим изменения">
        <button
          className={mode === "rescue" ? "selected" : ""}
          type="button"
          role="tab"
          aria-selected={mode === "rescue"}
          onClick={() => onModeChange("rescue")}
        >
          <RefreshCw size={14} aria-hidden="true" /> Планы поменялись
        </button>
        <button
          className={mode === "what_if" ? "selected" : ""}
          type="button"
          role="tab"
          aria-selected={mode === "what_if"}
          onClick={() => onModeChange("what_if")}
        >
          <FlaskConical size={14} aria-hidden="true" /> А что если…
        </button>
      </div>
      <form onSubmit={onSubmit}>
        <label htmlFor="decision-message">
          {mode === "rescue" ? "Что обязательно нужно изменить?" : "Какой сценарий сравнить?"}
        </label>
        <div>
          <input
            id="decision-message"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder={mode === "rescue" ? "Нужно вернуться до 8 утра" : "А если вернуться до 10?"}
          />
          <button type="submit" disabled={isRunning || !draft.trim()}>
            {isRunning ? "Сравниваю…" : mode === "rescue" ? "Спасти поездку" : "Сравнить"}
          </button>
        </div>
      </form>
      {mode === "what_if" && (isRunning || result) ? (
        <p className="simulation-note">Текущий вариант не меняю — это отдельная симуляция.</p>
      ) : null}
      {error ? <p className="decision-error" role="alert">{error}</p> : null}
      {result ? <DecisionResults result={result} onApply={onApply} /> : null}
    </section>
  );
}

function DecisionResults({ result, onApply }: { result: DecisionResult; onApply: (candidate: DecisionCandidate) => void }) {
  const candidates = result.result.candidates ?? [];
  return (
    <div className="decision-results" aria-live="polite">
      {result.result.reasons?.map((reason) => <p key={reason}>{reason}</p>)}
      {!candidates.length ? <p>Подходящих вариантов пока нет.</p> : null}
      {candidates.map((candidate) => {
        const changed = candidate.replaced_components ?? candidate.impact?.components_changed ?? [];
        const preserved = candidate.preserved_components ?? candidate.impact?.components_preserved ?? [];
        return (
          <article className="decision-candidate" key={candidate.id}>
            <div className="decision-candidate-heading">
              <span>{result.kind === "rescue" ? "Меняем только необходимое" : "Что изменится"}</span>
              <strong>{formatMoney(candidate.journey.total_price)}</strong>
            </div>
            <h3>{candidate.summary?.headline ?? candidate.explanation?.headline ?? `Вариант №${candidate.rank ?? 1}`}</h3>
            {candidate.summary?.price_delta_label ? <b>{candidate.summary.price_delta_label}</b> : null}
            {candidate.impact?.savings ? <b>Экономия {formatMoney(candidate.impact.savings)}</b> : null}
            <div className="decision-component-grid">
              {preserved.length ? (
                <div><small>Что сохраняем</small>{preserved.map((item) => <span key={item}><Check size={13} />{componentLabel(item)}</span>)}</div>
              ) : null}
              {changed.length ? (
                <div><small>Что меняем</small>{changed.map((item) => <span key={item}><RefreshCw size={13} />{componentLabel(item)}</span>)}</div>
              ) : null}
            </div>
            {candidate.explanation?.summary ? <p>{candidate.explanation.summary}</p> : null}
            {candidate.explanation?.reasons?.length ? (
              <details>
                <summary>Почему этот вариант <ChevronDown size={14} /></summary>
                {candidate.explanation.reasons.map((reason) => <p key={reason.text}>✓ {reason.text}</p>)}
                {candidate.explanation.tradeoffs?.map((tradeoff) => <p key={tradeoff.text}>• {tradeoff.text}</p>)}
              </details>
            ) : null}
            {candidate.relaxations?.length ? (
              <div className="decision-relaxations">
                <strong>Ближайший компромисс</strong>
                {candidate.relaxations.map((item) => <p key={`${item.title}-${item.description}`}>{item.description}</p>)}
              </div>
            ) : null}
            {candidate.insights?.map((insight) => (
              <aside className="journey-insight" key={`${insight.title}-${insight.description}`}>
                <strong>Ещё один момент: {insight.title}</strong>
                <p>{insight.description}</p>
              </aside>
            ))}
            {result.kind === "rescue" ? (
              <button className="apply-rescue-button" type="button" onClick={() => onApply(candidate)}>
                Применить изменение
              </button>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function componentLabel(value: string): string {
  return ({ outbound: "Дорога туда", inbound: "Дорога обратно", hotel: "Отель" } as Record<string, string>)[value] ?? value;
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(date);
}

function createGreeting(): ChatMessage {
  return { id: createUuid(), role: "assistant", content: INITIAL_MESSAGE };
}

function getOrCreateGuestUserId(): string {
  try {
    const storedUserId = window.localStorage.getItem(GUEST_USER_KEY);
    if (storedUserId) {
      return storedUserId;
    }
    const userId = createUuid();
    window.localStorage.setItem(GUEST_USER_KEY, userId);
    return userId;
  } catch {
    return createUuid();
  }
}

function createUuid(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10, 16).join(""),
  ].join("-");
}
