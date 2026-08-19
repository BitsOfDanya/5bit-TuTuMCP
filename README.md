# 5bit-TuTuMCP

Учебный сервис путешествий на React и FastAPI. Интерфейс вдохновлён структурой
главной страницы travel-сервиса, но явно помечен как прототип и не предназначен
для сбора данных от чужих аккаунтов.

## Что реализовано

- адаптивная главная: hero, продуктовые вкладки, поиск, промо, подборки и footer;
- кнопки разделов и бронирования работают как информативные заглушки;
- собственная авторизация по одноразовому коду или email/password;
- пользователи и одноразовые challenge хранятся в SQLite;
- пароль хешируется Argon2, сессия хранится в подписанной HttpOnly cookie;
- существующий LangChain agent API сохранён;
- компонентные, accessibility и FastAPI-тесты.

## Backend

Требуется Python 3.12+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
fastapi dev
```

API и OpenAPI доступны на `http://127.0.0.1:8000` и
`http://127.0.0.1:8000/docs`.

Чтобы вызвать сохранённого агента:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hello!"}'
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Откройте `http://127.0.0.1:5173`. Vite проксирует `/api` на FastAPI.

При `AUTH_DEBUG=true` одноразовый код показывается прямо в модальном окне.
Перед production-запуском задайте случайный `AUTH_SECRET_KEY`, выключите
`AUTH_DEBUG` и подключите реальную доставку кода через email/SMS-провайдера.

## Проверки

```bash
cd frontend
npm run build
npm test

cd ../backend
.venv/bin/ruff check app tests
.venv/bin/pytest -q
```

После `npm run build` FastAPI автоматически раздаёт `frontend/dist` с корня.
