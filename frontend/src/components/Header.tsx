import {
  BookOpen,
  ChevronDown,
  Heart,
  LogIn,
  LogOut,
  Menu,
  Route,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useState } from "react";

import type { User } from "../types";
import { Logo } from "./Logo";

interface HeaderProps {
  user: User | null;
  onLogin: () => void;
  onLogout: () => void;
  onStub: (message: string) => void;
}

const navigation = [
  { label: "Это выгодно!", icon: Sparkles },
  { label: "Автопутешествия", icon: Route },
  { label: "Маршруты", icon: Route },
  { label: "Справочная", icon: BookOpen },
  { label: "Путеводитель", icon: BookOpen },
  { label: "Избранное", icon: Heart },
] as const;

export function Header({ user, onLogin, onLogout, onStub }: HeaderProps) {
  const [isUserMenuOpen, setUserMenuOpen] = useState(false);

  return (
    <header className="site-header">
      <a className="logo-link" href="/" aria-label="На главную">
        <Logo />
      </a>

      <nav className="top-navigation" aria-label="Основная навигация">
        {navigation.map(({ label, icon: Icon }) => (
          <button
            className="top-nav-link"
            key={label}
            type="button"
            onClick={() => onStub(label + ": раздел пока в разработке")}
          >
            {label === "Избранное" ? <Icon size={13} aria-hidden="true" /> : null}
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="header-actions">
        {user ? (
          <div className="user-menu">
            <button
              className="login-button user-button"
              type="button"
              aria-expanded={isUserMenuOpen}
              onClick={() => setUserMenuOpen((value) => !value)}
            >
              <UserRound size={16} aria-hidden="true" />
              <span>{user.display_name}</span>
              <ChevronDown size={14} aria-hidden="true" />
            </button>
            {isUserMenuOpen ? (
              <div className="user-popover">
                <strong>{user.display_name}</strong>
                <span>{user.login}</span>
                <button
                  type="button"
                  onClick={() => {
                    setUserMenuOpen(false);
                    onLogout();
                  }}
                >
                  <LogOut size={16} aria-hidden="true" />
                  Выйти
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <button className="login-button" type="button" onClick={onLogin}>
            <LogIn size={15} aria-hidden="true" />
            Войти
          </button>
        )}
        <button
          className="menu-button"
          type="button"
          aria-label="Открыть меню"
          onClick={() => onStub("Меню пока в разработке")}
        >
          <Menu size={21} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
