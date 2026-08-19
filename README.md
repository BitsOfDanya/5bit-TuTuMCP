# 5bit-TuTuMCP

Учебный сервис путешествий на React и FastAPI. Интерфейс вдохновлён структурой
главной страницы travel-сервиса, но явно помечен как прототип и не предназначен
для сбора данных от чужих аккаунтов.

## Что реализовано

- адаптивная главная: hero, продуктовые вкладки, поиск, промо, подборки и footer;
- найденные варианты можно сохранить и оформить через серверный `create_checkout_link` Tutu;
- собственная авторизация по одноразовому коду или email/password;
- пользователи и одноразовые challenge хранятся в SQLite;
- пароль хешируется Argon2, сессия хранится в подписанной HttpOnly cookie;
- история чатов хранится по пользователям в SQLite и управляется через Alembic;
- LangGraph-агент вынесен в отдельный stateless `ai-service`;
- `constraint-negotiator` подключён к агенту как инструмент поиска и ослабления ограничений;
- Trip Rescue меняет только затронутую часть принятой поездки и предлагает ближайший компромисс;
- What-if сравнивает гипотезу без изменения принятой поездки, а Decision Explanation объясняет выбор;
- Preference Learning, Cold Start и Group Preferences персонализируют обычный поиск и Rescue;
- найденный Jarvell вариант можно передать в Smart Trip Tracker и отслеживать прямо во frontend;
- международные документы распознаются из PNG, JPEG и PDF;
- компонентные, accessibility и FastAPI-тесты.

## Архитектура

```text
frontend -> backend :8000 -> ai-service :8020 -> OpenAI
              |                   +-> constraint-negotiator :8010 -> Tutu MCP
              +-> trip-rescue :8030 -> Tutu MCP / OpenAI
              +-> smart-trip-tracker :8001 -> Tutu MCP
```

- `backend` владеет авторизацией, SQLite/Alembic и полной историей диалогов;
- `ai-service` владеет LangGraph, OpenAI, инструментами и распознаванием документов;
- `constraint-negotiator` ищет варианты и предлагает ослабление ограничений;
- `smart-trip-tracker` хранит историю цены выбранной комбинации и формирует рекомендацию;
- `trip-rescue` владеет Rescue, What-if, explanations и persistent preference profiles;
- frontend продолжает работать только с публичным backend API.

## Запуск AI-сервисов

### Быстрый локальный запуск

Первичная установка всех Python/Node-зависимостей и миграций:

```bash
make setup
```

Укажите `OPENAI_API_KEY` в корневом `.env`, затем поднимите всю цепочку одной командой:

```bash
make dev
```

Команда запускает и дожидается готовности:

- frontend — `http://127.0.0.1:5173`;
- backend — `http://127.0.0.1:8000`;
- smart-trip-tracker — `http://127.0.0.1:8001`;
- constraint-negotiator — `http://127.0.0.1:8010`;
- ai-service — `http://127.0.0.1:8020`.
- trip-rescue — `http://127.0.0.1:8030`.

Логи находятся в `.local/logs`. Для реального end-to-end запроса через всю цепочку
выполните в другом терминале:

```bash
make smoke
```

`make smoke` отправляет полный маршрут через Vite proxy и публичный backend API, проверяет
сохранение истории, OpenAI-агента и инструмент `constraint-negotiator`. Вызов использует
OpenAI API и внешний Tutu MCP.

### Как проверить Decision Intelligence в интерфейсе

1. Откройте `http://127.0.0.1:5173` и войдите в аккаунт.
2. В карточке «Какой вы путешественник?» нажмите «Получить» и сделайте четыре выбора.
3. В Джарвелле запросите поездку туда и обратно, затем нажмите «Выбрать поездку».
4. В появившемся блоке используйте «Планы поменялись» для Rescue или «А что если…» для
   отдельной симуляции. Кнопка «Оформить на Tutu» использует checkout URL, созданный на backend.
5. Для нескольких пассажиров нажмите «Создать группу» и добавьте profile ID остальных участников.

После перезагрузки принятая поездка остаётся доступной. Личный профиль хранится отдельно,
а групповой профиль вычисляется заново и не изменяет персональные preferences.

### Ручной запуск

Сначала запустите constraint negotiator:

```bash
cd constraint-negotiator
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Затем Jarvell AI Service:

```bash
cd ../ai-service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
fastapi dev
```

Для локального перехода `ai-service` также читает уже настроенный ключ из
`backend/.env`. После переноса ключа в `ai-service/.env` fallback можно удалить.

## Backend

Требуется Python 3.12+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
fastapi dev
```

API и OpenAPI доступны на `http://127.0.0.1:8000` и
`http://127.0.0.1:8000/docs`.

Чтобы вызвать сохранённого агента:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111","message":"Нужен поезд из Москвы в Казань 1 сентября, нас двое, бюджет 20000 рублей"}'
```

Backend обращается к `AI_SERVICE_URL` (по умолчанию `http://127.0.0.1:8020`). Ответ содержит
`session_id`, нормализованный `trip`, план, использованные инструменты,
`next_action` и `redirect_url`. Для продолжения диалога передавайте тот же `session_id`.

Readiness всей внутренней цепочки доступен на `GET http://127.0.0.1:8000/ready`.

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
.venv/bin/python -m pytest -q
.venv/bin/alembic check

cd ../ai-service
.venv/bin/ruff check app tests
.venv/bin/python -m pytest -q

cd ../trip-rescue
.venv/bin/python -m pytest -q
```

После `npm run build` FastAPI автоматически раздаёт `frontend/dist` с корня.

## Production

Production-образы, Caddy, GHCR CI, deploy/rollback и резервное копирование описаны в
[DEPLOYMENT.md](DEPLOYMENT.md). Основная команда развёртывания:

```bash
make prod-deploy ENV_FILE=.env.production
```
