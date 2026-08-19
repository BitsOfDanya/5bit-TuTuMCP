import {
  BadgePercent,
  CheckCircle2,
  Headphones,
  Layers3,
  Plane,
  ShieldCheck,
  Star,
  TrainFront,
} from "lucide-react";
import { FormEvent } from "react";

import type { User } from "../types";
import { Header } from "./Header";
import { SearchPanel } from "./SearchPanel";

interface HomePageProps {
  user: User | null;
  onLogin: () => void;
  onLogout: () => void;
  onOpenAssistant: () => void;
  onStub: (message: string) => void;
}

const deals = [
  {
    type: "plane",
    route: "Москва — Баку",
    date: "27 сен в 03:15",
    duration: "3ч 20м · прямой",
    price: "9 237 ₽",
    oldPrice: "13 393 ₽",
    discount: "−31%",
  },
  {
    type: "plane",
    route: "Москва — Сочи",
    date: "1 окт в 16:50",
    duration: "3ч 45м · прямой",
    price: "10 430 ₽",
    oldPrice: "11 430 ₽",
    discount: "−8%",
  },
  {
    type: "plane",
    route: "Москва — Новосибирск",
    date: "2 окт в 08:25",
    duration: "4ч · прямой",
    price: "10 130 ₽",
    oldPrice: "11 870 ₽",
    discount: "−14%",
  },
  {
    type: "plane",
    route: "Новосибирск — Москва",
    date: "15 сен в 08:25",
    duration: "4ч 20м · прямой",
    price: "10 156 ₽",
    oldPrice: "11 896 ₽",
    discount: "−14%",
  },
  {
    type: "plane",
    route: "Москва — Махачкала",
    date: "5 сен в 17:00",
    duration: "3ч · прямой",
    price: "5 653 ₽",
    oldPrice: "6 103 ₽",
    discount: "−8%",
  },
] as const;

const hotels = [
  { city: "Сочи", name: "Отель у моря", rating: "9,2", price: "от 4 840 ₽", tone: "sea" },
  { city: "Санкт-Петербург", name: "Дом на Невском", rating: "9,4", price: "от 5 120 ₽", tone: "city" },
  { city: "Москва", name: "Садовое кольцо", rating: "8,9", price: "от 4 640 ₽", tone: "night" },
  { city: "Казань", name: "Гостиница у Кремля", rating: "9,1", price: "от 3 970 ₽", tone: "sunset" },
] as const;

const directions = [
  ["Москва — Санкт-Петербург", "от 5 ч 20 м", "от 5 711 ₽"],
  ["Москва — Нижний Новгород", "от 3 ч 48 м", "от 2 569 ₽"],
  ["Москва — Ярославль", "от 3 ч 24 м", "от 1 181 ₽"],
  ["Москва — Рязань", "от 2 ч 5 м", "от 1 723 ₽"],
  ["Москва — Тула", "от 2 ч 25 м", "от 1 136 ₽"],
  ["Москва — Владимир", "от 1 ч 45 м", "от 1 844 ₽"],
] as const;

const features = [
  {
    icon: ShieldCheck,
    title: "Оплата позже",
    text: "Можно зафиксировать цену на билет и выкупить позже",
  },
  {
    icon: BadgePercent,
    title: "Кешбэк баллами",
    text: "Получайте баллы за путешествия и оплачивайте ими новые поездки",
  },
  {
    icon: Headphones,
    title: "Поддержка 24/7",
    text: "Поможем в чате, по электронной почте и телефону",
  },
  {
    icon: Layers3,
    title: "Всё и сразу",
    text: "Сравнивайте разные виды транспорта в одном месте",
  },
] as const;

export function HomePage({
  user,
  onLogin,
  onLogout,
  onOpenAssistant,
  onStub,
}: HomePageProps) {
  function handleNewsletter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onStub("Спасибо! Подписка пока работает как демонстрация");
  }

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-glow hero-glow-one" />
        <div className="hero-glow hero-glow-two" />
        <div className="page-container">
          <Header user={user} onLogin={onLogin} onLogout={onLogout} onStub={onStub} />

          <button
            className="hero-banner"
            type="button"
            onClick={() => onStub("Промо-предложение пока недоступно")}
          >
            <span className="banner-ticket">✈</span>
            <strong>АВИАБИЛЕТЫ С КЕШБЭКОМ 3%</strong>
            <span className="banner-plane">🛫</span>
          </button>

          <div className="hero-heading-row">
            <div>
              <span className="prototype-label">Учебный прототип · не официальный tutu.ru</span>
              <h1>Путешествуйте выгодно</h1>
              <div className="trust-pills" aria-label="Преимущества сервиса">
                <span><ShieldCheck size={14} />22 года работаем для вас</span>
                <span><Plane size={14} />42 млн путешествуют с нами</span>
                <span><Star size={14} fill="currentColor" />4,84 — рейтинг приложения</span>
              </div>
            </div>
            <aside className="traveller-card">
              <span className="traveller-kicker">КАКОЙ ВЫ ПУТЕШЕСТВЕННИК?</span>
              <p>Ответьте на несколько вопросов — подберём идеи для поездки</p>
              <button type="button" onClick={() => onStub("Тест путешественника пока не готов")}>
                Получить
              </button>
            </aside>
          </div>

          <SearchPanel onOpenAssistant={onOpenAssistant} onStub={onStub} />
        </div>
      </section>

      <main className="main-surface">
        <div className="page-container">
          <section className="promo-strip">
            <div>
              <h2>Море + скидки до 25%</h2>
              <p>Отдыхайте за границей выгодно и без визы</p>
              <button type="button" onClick={() => onStub("Подбор билетов пока недоступен")}>
                Найти билеты
              </button>
            </div>
            <div className="promo-art" aria-hidden="true">
              <span className="promo-sun" />
              <span className="promo-wave promo-wave-one" />
              <span className="promo-wave promo-wave-two" />
              <span className="promo-suitcase">🧳</span>
              <strong>ЛЕТО<br />ПРОДОЛЖАЕТСЯ</strong>
            </div>
          </section>

          <section className="content-section deals-section">
            <div className="section-heading">
              <div>
                <h2>Это выгодно!</h2>
                <p>Цены ниже средних за последние 10 дней. Обновляем постоянно</p>
              </div>
              <button type="button" onClick={() => onStub("Все предложения пока недоступны")}>
                Показать все
              </button>
            </div>
            <div className="filter-pills" aria-label="Фильтр предложений">
              <button className="selected" type="button">Все</button>
              <button type="button">Самолёты</button>
              <button type="button">Поезда</button>
            </div>
            <div className="deal-grid">
              {deals.map((deal) => (
                <button
                  className="deal-card"
                  key={deal.route}
                  type="button"
                  onClick={() => onStub(deal.route + ": бронирование пока недоступно")}
                >
                  {deal.type === "plane" ? (
                    <Plane className="deal-icon" size={24} aria-hidden="true" />
                  ) : (
                    <TrainFront className="deal-icon" size={24} aria-hidden="true" />
                  )}
                  <strong>{deal.route}</strong>
                  <span>{deal.date}</span>
                  <small>{deal.duration}</small>
                  <div className="deal-price">
                    <b>{deal.price}</b>
                    <em>{deal.discount}</em>
                  </div>
                  <del>{deal.oldPrice}</del>
                </button>
              ))}
            </div>
          </section>

          <section className="content-section">
            <div className="section-heading">
              <div>
                <h2>Отели по суперцене</h2>
                <p>Классные варианты с выгодой — специально для вас</p>
              </div>
              <button type="button" onClick={() => onStub("Каталог отелей пока недоступен")}>
                Все отели
              </button>
            </div>
            <div className="hotel-grid">
              {hotels.map((hotel) => (
                <button
                  className="hotel-card"
                  key={hotel.name}
                  type="button"
                  onClick={() => onStub(hotel.name + ": карточка пока недоступна")}
                >
                  <span className={"hotel-image hotel-" + hotel.tone} aria-hidden="true">
                    <span>✦</span>
                  </span>
                  <span className="hotel-content">
                    <span className="hotel-rating">{hotel.rating}</span>
                    <small>{hotel.city}</small>
                    <strong>{hotel.name}</strong>
                    <b>{hotel.price}</b>
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="content-section weekend-section">
            <div className="section-heading">
              <div>
                <h2>Развеяться на выходных на поезде</h2>
                <p>Популярные короткие маршруты из Москвы</p>
              </div>
            </div>
            <div className="direction-grid">
              {directions.map(([route, duration, price]) => (
                <button
                  className="direction-card"
                  key={route}
                  type="button"
                  onClick={() => onStub(route + ": поиск пока недоступен")}
                >
                  <TrainFront size={28} aria-hidden="true" />
                  <strong>{route}</strong>
                  <span>{duration} в пути</span>
                  <b>{price}</b>
                </button>
              ))}
            </div>
          </section>

          <section className="content-section">
            <div className="section-heading">
              <div><h2>Фишки Туту demo</h2></div>
            </div>
            <div className="feature-grid">
              {features.map(({ icon: Icon, title, text }) => (
                <article className="feature-card" key={title}>
                  <span><Icon size={28} aria-hidden="true" /></span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="newsletter">
            <div>
              <span>Письма для тех, кто любит путешествия</span>
              <h2>Мы вам — акции и классные места, а вы нам — почту</h2>
            </div>
            <form onSubmit={handleNewsletter}>
              <label className="visually-hidden" htmlFor="newsletter-email">
                Электронная почта
              </label>
              <input id="newsletter-email" type="email" placeholder="Электронная почта" required />
              <button type="submit">Подписаться</button>
              <label className="newsletter-consent">
                <input type="checkbox" required />
                <span>Согласен на обработку данных и рекламные рассылки</span>
              </label>
            </form>
          </section>

          <section className="about-section">
            <div>
              <span className="about-mark">ту</span>
              <h2>Билеты и отели онлайн для ваших путешествий</h2>
              <p>
                Планируйте поездку целиком: сравнивайте транспорт, выбирайте отели
                и сохраняйте понравившиеся варианты в одном месте.
              </p>
            </div>
            <div className="about-points">
              <p><CheckCircle2 size={20} />Удобный поиск по направлениям</p>
              <p><CheckCircle2 size={20} />Собственная безопасная авторизация</p>
              <p><CheckCircle2 size={20} />Поддержка на каждом этапе поездки</p>
            </div>
          </section>
        </div>
      </main>

      <footer className="footer">
        <div className="page-container footer-grid">
          <div>
            <strong>Путешественникам</strong>
            <button type="button">Программа лояльности</button>
            <button type="button">Путеводитель</button>
          </div>
          <div>
            <strong>Партнёрам</strong>
            <button type="button">Стать партнёром</button>
            <button type="button">Реклама</button>
          </div>
          <div>
            <strong>Помощь</strong>
            <button type="button">Справочная</button>
            <button type="button">Обратная связь</button>
          </div>
          <div>
            <strong>Туту demo</strong>
            <p>Учебный проект React + FastAPI. Не является официальным сайтом tutu.ru.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
