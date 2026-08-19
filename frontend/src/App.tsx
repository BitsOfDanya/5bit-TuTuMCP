import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { getSession, logout } from "./api/auth";
import { AuthModal } from "./components/AuthModal";
import { ChatWidget } from "./components/ChatWidget";
import { HomePage } from "./components/HomePage";
import type { AuthSession, User } from "./types";

const BookingFlowPage = lazy(() =>
  import("./components/BookingFlowPage").then((module) => ({ default: module.BookingFlowPage })),
);

export function App() {
  const queryClient = useQueryClient();
  const [isAuthOpen, setAuthOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [locationPath, setLocationPath] = useState(() => window.location.pathname);
  const toastTimer = useRef<number | null>(null);
  const sessionQuery = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  });

  useEffect(() => {
    const handlePopState = () => setLocationPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
      if (toastTimer.current !== null) {
        window.clearTimeout(toastTimer.current);
      }
    };
  }, []);

  const user = sessionQuery.data?.user ?? null;

  function navigate(path: string) {
    window.history.pushState({}, "", path);
    setLocationPath(window.location.pathname);
  }

  function notify(message: string) {
    setToast(message);
    if (toastTimer.current !== null) {
      window.clearTimeout(toastTimer.current);
    }
    toastTimer.current = window.setTimeout(() => setToast(""), 4200);
  }

  function handleAuthenticated(authenticatedUser: User) {
    queryClient.setQueryData<AuthSession>(["auth-session"], {
      user: authenticatedUser,
    });
    notify("Готово! Вы вошли в свой аккаунт.");
  }

  async function handleLogout() {
    try {
      await logout();
      queryClient.setQueryData<AuthSession>(["auth-session"], { user: null });
      notify("Вы вышли из аккаунта.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Не удалось выйти из аккаунта.");
    }
  }

  const bookingMatch = locationPath.match(/^\/booking\/([0-9a-f-]+)$/i);
  if (bookingMatch) {
    const bookingUserId = new URLSearchParams(window.location.search).get("user_id");
    if (bookingUserId) {
      return (
        <Suspense fallback={<main className="booking-loading">Загружаю оформление…</main>}>
          <BookingFlowPage
            bookingId={bookingMatch[1]}
            userId={bookingUserId}
            onBack={() => navigate("/")}
          />
        </Suspense>
      );
    }
  }

  return (
    <>
      <HomePage
        user={user}
        onLogin={() => setAuthOpen(true)}
        onLogout={handleLogout}
        onStub={notify}
      />
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setAuthOpen(false)}
        onAuthenticated={handleAuthenticated}
        onStub={notify}
      />
      <ChatWidget key={user?.id ?? "guest"} user={user} />
      {toast ? (
        <div className="toast" role="status">
          <span>{toast}</span>
          <button type="button" aria-label="Закрыть уведомление" onClick={() => setToast("")}>
            <X size={17} aria-hidden="true" />
          </button>
        </div>
      ) : null}
    </>
  );
}
