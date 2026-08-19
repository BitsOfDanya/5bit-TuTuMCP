import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getSession, logout } from "./api/auth";
import { AuthModal } from "./components/AuthModal";
import { ChatWidget } from "./components/ChatWidget";
import type { ChatExperience } from "./components/ChatWidget";
import { HomePage } from "./components/HomePage";
import type { AuthSession, User } from "./types";

export function App() {
  const queryClient = useQueryClient();
  const [isAuthOpen, setAuthOpen] = useState(false);
  const [isChatOpen, setChatOpen] = useState(false);
  const [chatExperience, setChatExperience] = useState<ChatExperience>("chat");
  const [toast, setToast] = useState("");
  const toastTimer = useRef<number | null>(null);
  const sessionQuery = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  });

  useEffect(() => {
    return () => {
      if (toastTimer.current !== null) {
        window.clearTimeout(toastTimer.current);
      }
    };
  }, []);

  const user = sessionQuery.data?.user ?? null;

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

  function openChat(experience: ChatExperience) {
    setChatExperience(experience);
    setChatOpen(true);
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

  return (
    <>
      <HomePage
        user={user}
        onLogin={() => setAuthOpen(true)}
        onLogout={handleLogout}
        onOpenAssistant={() => openChat("chat")}
        onOpenPreferences={() => openChat("preferences")}
        onStub={notify}
      />
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => {
          setAuthOpen(false);
        }}
        onAuthenticated={handleAuthenticated}
        onStub={notify}
      />
      <ChatWidget
        key={user?.id ?? "guest"}
        user={user}
        isOpen={isChatOpen}
        onOpenChange={setChatOpen}
        experience={chatExperience}
        onExperienceChange={setChatExperience}
        onRequireAuth={() => {
          setAuthOpen(true);
          notify("Войдите, чтобы сохранить поездку и использовать Decision Intelligence.");
        }}
        onNotify={notify}
      />
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
