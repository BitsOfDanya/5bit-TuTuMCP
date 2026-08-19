import { ArrowLeft, Eye, EyeOff, X } from "lucide-react";
import { FormEvent, useState } from "react";

import {
  passwordAuth,
  registerAccount,
  requestCode,
  verifyCode,
} from "../api/auth";
import type { User } from "../types";

type AuthMode = "identifier" | "code" | "password" | "register";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthenticated: (user: User) => void;
  onStub: (message: string) => void;
}

export function AuthModal({
  isOpen,
  onClose,
  onAuthenticated,
  onStub,
}: AuthModalProps) {
  const [mode, setMode] = useState<AuthMode>("identifier");
  const [login, setLogin] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [registrationEmail, setRegistrationEmail] = useState("");
  const [registrationPassword, setRegistrationPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [isPasswordVisible, setPasswordVisible] = useState(false);
  const [isSubmitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) {
    return null;
  }

  function closeModal() {
    setMode("identifier");
    setError("");
    setCode("");
    setPassword("");
    setRegistrationPassword("");
    setPasswordConfirmation("");
    setDebugCode(null);
    onClose();
  }

  async function handleCodeRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const result = await requestCode(login);
      setChallengeId(result.challenge_id);
      setDebugCode(result.debug_code);
      setMode("code");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCodeVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const result = await verifyCode(challengeId, code);
      if (result.user) {
        onAuthenticated(result.user);
        closeModal();
      }
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePasswordAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const result = await passwordAuth(email, password);
      if (result.user) {
        onAuthenticated(result.user);
        closeModal();
      }
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (registrationPassword !== passwordConfirmation) {
      setError("Пароли не совпадают.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await registerAccount(name, registrationEmail, registrationPassword);
      if (result.user) {
        onAuthenticated(result.user);
        closeModal();
      }
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) {
          closeModal();
        }
      }}
    >
      <section
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
      >
        <div className="auth-modal-controls">
          {mode !== "identifier" ? (
            <button
              className="round-icon-button"
              type="button"
              aria-label="Назад"
              onClick={() => {
                setError("");
                setMode("identifier");
              }}
            >
              <ArrowLeft size={20} aria-hidden="true" />
            </button>
          ) : (
            <span />
          )}
          <button
            className="round-icon-button"
            type="button"
            aria-label="Закрыть"
            onClick={closeModal}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <p className="auth-safety-note">
          Учебный прототип. Не вводите пароль от tutu.ru.
        </p>

        {mode === "identifier" ? (
          <>
            <h2 id="auth-title">Войдите или зарегистрируйтесь</h2>
            <form className="auth-form" onSubmit={handleCodeRequest}>
              <label className="visually-hidden" htmlFor="auth-login">
                Телефон или электронная почта
              </label>
              <input
                autoFocus
                id="auth-login"
                name="login"
                placeholder="Ваш телефон или почта"
                autoComplete="username"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
              />
              <button className="primary-auth-button" disabled={isSubmitting} type="submit">
                {isSubmitting ? "Отправляем…" : "Отправить код"}
              </button>
            </form>
            <button
              className="secondary-auth-button"
              type="button"
              onClick={() => {
                setError("");
                setMode("password");
              }}
            >
              Войти другим способом
            </button>
            <button
              className="auth-switch-button"
              type="button"
              onClick={() => {
                setError("");
                setMode("register");
              }}
            >
              Зарегистрироваться по почте
            </button>
            <div className="social-auth">
              <span>или войдите с помощью</span>
              <div>
                <button
                  className="social-button social-ok"
                  type="button"
                  aria-label="Войти через Одноклассники"
                  onClick={() => onStub("Вход через Одноклассники пока не подключён")}
                >
                  OK
                </button>
                <button
                  className="social-button social-vk"
                  type="button"
                  aria-label="Войти через ВКонтакте"
                  onClick={() => onStub("Вход через ВКонтакте пока не подключён")}
                >
                  VK
                </button>
              </div>
            </div>
            <AuthLegal copy="Отправить код" />
          </>
        ) : null}

        {mode === "code" ? (
          <>
            <h2 id="auth-title">Введите код</h2>
            <p className="auth-description">
              {debugCode
                ? "В локальном режиме письмо не отправляется — используйте код ниже."
                : <>Мы отправили шестизначный код на <strong>{login}</strong></>}
            </p>
            {debugCode ? (
              <p className="debug-code">Код для локальной разработки: {debugCode}</p>
            ) : null}
            <form className="auth-form" onSubmit={handleCodeVerify}>
              <label className="visually-hidden" htmlFor="auth-code">
                Код подтверждения
              </label>
              <input
                autoFocus
                id="auth-code"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                placeholder="000000"
                autoComplete="one-time-code"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
              />
              <button
                className="primary-auth-button"
                disabled={isSubmitting || code.length !== 6}
                type="submit"
              >
                {isSubmitting ? "Проверяем…" : "Продолжить"}
              </button>
            </form>
          </>
        ) : null}

        {mode === "password" ? (
          <>
            <h2 id="auth-title">Введите почту и пароль</h2>
            <form className="auth-form" onSubmit={handlePasswordAuth}>
              <label className="visually-hidden" htmlFor="auth-email">
                Электронная почта
              </label>
              <input
                autoFocus
                id="auth-email"
                type="email"
                placeholder="Ваша почта"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <label className="password-field">
                <span className="visually-hidden">Пароль</span>
                <input
                  type={isPasswordVisible ? "text" : "password"}
                  placeholder="Пароль"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  aria-label={isPasswordVisible ? "Скрыть пароль" : "Показать пароль"}
                  onClick={() => setPasswordVisible((visible) => !visible)}
                >
                  {isPasswordVisible ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </label>
              <button
                className="forgot-password"
                type="button"
                onClick={() => onStub("Восстановление пароля пока не подключено")}
              >
                Не помню пароль
              </button>
              <button
                className="primary-auth-button"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? "Входим…" : "Войти"}
              </button>
            </form>
            <p className="password-help">
              Нет аккаунта?{" "}
              <button
                type="button"
                onClick={() => {
                  setError("");
                  setRegistrationEmail(email);
                  setMode("register");
                }}
              >
                Зарегистрироваться
              </button>
            </p>
            <AuthLegal copy="Войти" />
          </>
        ) : null}

        {mode === "register" ? (
          <>
            <h2 id="auth-title">Создайте аккаунт</h2>
            <p className="auth-description">
              Регистрация работает по почте и паролю — код подтверждения не нужен.
            </p>
            <form className="auth-form" onSubmit={handleRegistration}>
              <label className="visually-hidden" htmlFor="registration-name">
                Имя
              </label>
              <input
                autoFocus
                id="registration-name"
                type="text"
                placeholder="Ваше имя"
                autoComplete="name"
                minLength={2}
                maxLength={80}
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <label className="visually-hidden" htmlFor="registration-email">
                Электронная почта
              </label>
              <input
                id="registration-email"
                type="email"
                placeholder="Ваша почта"
                autoComplete="email"
                required
                value={registrationEmail}
                onChange={(event) => setRegistrationEmail(event.target.value)}
              />
              <label className="visually-hidden" htmlFor="registration-password">
                Придумайте пароль
              </label>
              <input
                id="registration-password"
                type="password"
                placeholder="Придумайте пароль"
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
                value={registrationPassword}
                onChange={(event) => setRegistrationPassword(event.target.value)}
              />
              <label className="visually-hidden" htmlFor="registration-password-confirmation">
                Повторите пароль
              </label>
              <input
                id="registration-password-confirmation"
                type="password"
                placeholder="Повторите пароль"
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
                value={passwordConfirmation}
                onChange={(event) => setPasswordConfirmation(event.target.value)}
              />
              <button
                className="primary-auth-button"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? "Создаём аккаунт…" : "Зарегистрироваться"}
              </button>
            </form>
            <AuthLegal copy="Зарегистрироваться" />
          </>
        ) : null}

        {error ? <p className="auth-error" role="alert">{error}</p> : null}
      </section>
    </div>
  );
}

function AuthLegal({ copy }: { copy: string }) {
  return (
    <p className="auth-legal">
      Нажимая кнопку «{copy}», вы принимаете{" "}
      <button type="button">пользовательское соглашение</button>
      <br />
      <button type="button">Политика обработки персональных данных</button>
    </p>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла ошибка. Попробуйте ещё раз.";
}
