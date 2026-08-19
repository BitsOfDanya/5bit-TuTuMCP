import { ArrowUpRight, SendHorizontal, Sparkles, X } from "lucide-react";
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
import type { SearchOption } from "../api/chat";
import type { User } from "../types";
import { TravelOptionCards } from "./TravelOptionCards";

const ChatMarkdown = lazy(() =>
  import("./ChatMarkdown").then((module) => ({ default: module.ChatMarkdown })),
);

const GUEST_USER_KEY = "tutumcp.chat.guest-user-id.v1";
const INITIAL_MESSAGE = [
  "Привет! Я **Джарвелл**, ваш помощник по путешествиям.",
  "",
  "Расскажите, куда и когда хотите поехать — я уточню детали и соберу параметры поиска.",
].join("\n");

const QUICK_PROMPTS = [
  "Найти поезд",
  "Подобрать перелёт",
  "Забронировать отель",
];

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  redirectUrl?: string | null;
  options?: SearchOption[];
}

interface ChatWidgetProps {
  user: User | null;
}

export function ChatWidget({ user }: ChatWidgetProps) {
  const [isOpen, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [createGreeting()]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isSending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [failedMessage, setFailedMessage] = useState("");
  const [guestUserId] = useState(getOrCreateGuestUserId);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const userId = user?.id ?? guestUserId;

  useEffect(() => {
    return () => abortControllerRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => textareaRef.current?.focus());

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        closeChat();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) {
        return;
      }

      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
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
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [isOpen, isSending, messages]);

  function openChat() {
    setOpen(true);
  }

  function closeChat() {
    setOpen(false);
    window.requestAnimationFrame(() => launcherRef.current?.focus());
  }

  async function submitMessage(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || isSending) {
      return;
    }

    setMessages((current) => [
      ...current,
      { id: createUuid(), role: "user", content: message },
    ]);
    setDraft("");
    setError("");
    setFailedMessage("");
    setSending(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await sendChatMessage(
        {
          user_id: userId,
          session_id: sessionId,
          message,
        },
        controller.signal,
      );
      setSessionId(response.session_id);
      setMessages((current) => [
        ...current,
        {
          id: createUuid(),
          role: "assistant",
          content: response.response,
          redirectUrl: response.redirect_url,
          options: response.search_options ?? [],
        },
      ]);
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(draft);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <>
      <button
        ref={launcherRef}
        className={`chat-launcher${isOpen ? " chat-launcher-hidden" : ""}`}
        type="button"
        aria-label="Открыть чат с Джарвеллом"
        aria-expanded={isOpen}
        aria-controls="jarvell-chat-dialog"
        aria-hidden={isOpen}
        tabIndex={isOpen ? -1 : 0}
        onClick={openChat}
      >
        <span className="chat-launcher-icon" aria-hidden="true">
          <Sparkles size={23} />
        </span>
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
              <span className="jarvell-avatar" aria-hidden="true">
                <Sparkles size={21} />
              </span>
              <div>
                <h2 id="jarvell-chat-title">Джарвелл</h2>
                <p id="jarvell-chat-description">
                  <span aria-hidden="true" /> На связи · AI-помощник tutu
                </p>
              </div>
              <button type="button" aria-label="Закрыть чат" onClick={closeChat}>
                <X size={20} aria-hidden="true" />
              </button>
            </header>

            <div className="chat-messages" aria-live="polite" aria-busy={isSending}>
              <p className="chat-date-marker">Сегодня</p>
              {messages.map((message) => (
                <article
                  className={`chat-message chat-message-${message.role}${message.options?.length ? " chat-message-has-options" : ""}`}
                  key={message.id}
                >
                  {message.role === "assistant" ? (
                    <span className="message-avatar" aria-hidden="true">
                      J
                    </span>
                  ) : null}
                  <div className="chat-bubble">
                    <Suspense fallback={<span>Загружаю сообщение…</span>}>
                      <ChatMarkdown content={message.content} />
                    </Suspense>
                    <TravelOptionCards options={message.options ?? []} />
                    {message.redirectUrl && !message.options?.length ? (
                      <a className="chat-redirect" href={message.redirectUrl}>
                        Перейти к вариантам
                        <ArrowUpRight size={15} aria-hidden="true" />
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
                      onClick={() => void submitMessage(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              ) : null}

              {isSending ? (
                <div className="chat-typing" role="status" aria-label="Джарвелл печатает">
                  <span />
                  <span />
                  <span />
                </div>
              ) : null}

              {error ? (
                <div className="chat-error" role="alert">
                  <span>{error}</span>
                  <button type="button" onClick={() => void submitMessage(failedMessage)}>
                    Повторить
                  </button>
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-composer" onSubmit={handleSubmit}>
              <label className="visually-hidden" htmlFor="jarvell-message">
                Сообщение Джарвеллу
              </label>
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
              <button
                type="submit"
                aria-label="Отправить сообщение"
                disabled={isSending || !draft.trim()}
              >
                <SendHorizontal size={19} aria-hidden="true" />
              </button>
              <p>Enter — отправить · Shift + Enter — новая строка</p>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
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
