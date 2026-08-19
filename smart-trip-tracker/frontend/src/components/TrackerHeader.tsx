import { ChevronDown, CircleHelp, UserRound } from "lucide-react";

const services = ["Отели", "Авиа", "Ж/д", "Автобусы"];

export function TrackerHeader() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="tutu-logo" href="/" aria-label="Туту — на главную">
          туту
        </a>
        <nav className="service-nav" aria-label="Сервисы для путешествий">
          {services.map((service) => (
            <a href="/" key={service}>
              {service}
            </a>
          ))}
          <button type="button">
            Ещё
            <ChevronDown size={14} aria-hidden="true" />
          </button>
        </nav>
        <div className="header-tools">
          <a href="/" aria-label="Помощь">
            <CircleHelp size={20} aria-hidden="true" />
            <span>Помощь</span>
          </a>
          <button className="profile-button" type="button" aria-label="Открыть профиль">
            <UserRound size={19} aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  );
}
