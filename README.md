# 5bit TuTuMCP — AI-помощник для путешествий

Учебный full-stack прототип, который собирает поездку в диалоге, ищет реальные варианты через
Tutu MCP, объясняет компромиссы, персонализирует выдачу, отслеживает цену и помогает перестроить
уже выбранный маршрут при изменении планов.

Проект состоит из React-интерфейса и пяти Python-сервисов. Единственная публичная точка входа
для frontend — общий FastAPI backend. Внутренние AI-сервисы не являются отдельными frontend API.

## Возможности

- диалоговый агент «Джарвелл» собирает и нормализует параметры поездки;
- поиск поездов, авиабилетов, автобусов и отелей через Tutu MCP;
- Constraint Negotiator находит варианты или предлагает минимальное ослабление ограничений;
- карточки готовых маршрутов с сегментами, ценой, ссылками и объяснениями;
- Price Intelligence отслеживает выбранную комбинацию и рекомендует купить или подождать;
- сохранение принятой поездки и восстановление её после перезагрузки;
- Trip Rescue заменяет только затронутые части принятого маршрута;
- What-if сравнивает альтернативу, не изменяя сохранённую поездку;
- Preference Cold Start, обучение по выбору и персональная переранжировка;
- групповой профиль и переранжировка по профилям участников;
- авторизация по одноразовому коду и email/password;
- извлечение данных пассажирских документов из PNG, JPEG и PDF;
- сохранение диалогов, миграции Alembic, health/readiness checks и production Compose.

## Финальная архитектура

```text
Browser
  |
  | /api/v1/* + HttpOnly session cookie
  v
Vite dev proxy / Caddy
  |
  v
backend :8000                         финальный orchestrator и публичный API
  |-- ai-service :8020                LangGraph agent, OpenAI, document extraction
  |     |-- constraint-negotiator :8010 -- Tutu MCP
  |     `-- smart-trip-tracker :8001 ---- Tutu MCP
  |-- trip-rescue :8030 ------------- Tutu MCP + OpenAI
  `-- smart-trip-tracker :8001 ------- Tutu MCP
```

Frontend никогда не обращается напрямую к `ai-service`, `constraint-negotiator`,
`trip-rescue` или `smart-trip-tracker`. Он может выполнять несколько запросов, но только к
публичному backend: поиск, принятие поездки, Rescue, Preferences и Price Intelligence доступны
под единым префиксом `/api/v1`.

### Ответственность компонентов

| Компонент | Порт | Ответственность | Persistence |
| --- | ---: | --- | --- |
| `frontend` | 5173 | React UI, чат, карточки, Rescue/What-if и Price Intelligence | состояние интерфейса |
| `backend` | 8000 | публичный API, orchestration, auth, диалоги, принятая поездка | SQLite + Alembic |
| `ai-service` | 8020 | stateless LangGraph agent, планирование, tool calls, OCR | нет |
| `constraint-negotiator` | 8010 | канонический `TripSpec`, поиск и ослабление ограничений | нет |
| `smart-trip-tracker` | 8001 | наблюдения цены и рекомендация покупки | SQLite |
| `trip-rescue` | 8030 | Rescue, What-if, explanations, личные и групповые preferences | JSON store |

В production Caddy завершает TLS, раздаёт собранный frontend и проксирует `/api` в backend.
Остальные сервисы доступны только во внутренней Docker-сети.

## Основной поток данных

1. Frontend отправляет сообщение в `POST /api/v1/agent/chat`.
2. Backend загружает историю `user_id + session_id` и вызывает stateless `ai-service`.
3. Агент возвращает нормализованный запрос, план и вызывает нужный инструмент:
   `negotiate_constraints` или `analyze_purchase_timing`.
4. Backend сохраняет диалог, при наличии авторизованного пользователя применяет персональную
   переранжировку и возвращает frontend один `AgentResponse`.
5. Пользователь принимает одну карточку через `PUT /api/v1/trips/current`.
6. Последующие Rescue и What-if получают сохранённые `TripSpec` и `JourneyOption` на backend —
   повторный parsing и повторный поиск исходной поездки frontend не выполняет.

## Идентификаторы и состояние

- `user_id` — UUID пользователя из `GET /api/v1/auth/me`; он же используется как
  `profile_id` Preference Learning.
- `session_id` — UUID диалога. Первый запрос может передать `null`; backend создаст ID, который
  нужно использовать в следующих сообщениях.
- `SearchOption.id` / `JourneyOption.id` — ID конкретного найденного варианта.
- `tracking_id` — UUID отслеживания цены, создаваемый Smart Trip Tracker.
- `group_id` — стабильный ID группы, задаваемый клиентом; состав передаётся в
  `participant_profile_ids`.

Текущая модель хранит ровно одну принятую поездку на пользователя в таблице
`accepted_itineraries`, где ключ — `user_id`. Публичный ресурс называется `/trips/current`, а
отдельного `trip_id` в текущем контракте нет. Для поддержки нескольких параллельных поездок
следующей версией контракта потребуется ввести `trip_id` и коллекцию `/api/v1/trips`.

## Публичный integration contract

Полная интерактивная схема доступна после запуска на
[`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs). Ниже перечислены основные фасады,
которые использует frontend.

### AI Agent

`POST /api/v1/agent/chat`

Request:

```json
{
  "user_id": "11111111-1111-1111-1111-111111111111",
  "session_id": null,
  "message": "Нужен поезд из Москвы в Казань 1 сентября, обратно 5 сентября, бюджет 30000 рублей"
}
```

Response верхнего уровня:

```json
{
  "user_id": "11111111-1111-1111-1111-111111111111",
  "session_id": "22222222-2222-2222-2222-222222222222",
  "response": "Нашёл подходящие варианты.",
  "trip": {
    "service_type": "train",
    "origin": "Москва",
    "destination": "Казань",
    "start_date": "2026-09-01",
    "end_date": "2026-09-05",
    "preferred_time": null,
    "passengers": 1,
    "budget": 30000,
    "currency": "RUB",
    "is_international": false
  },
  "missing_fields": [],
  "is_complete": true,
  "next_action": "redirect_to_search",
  "decision_intent": "search",
  "plan": {
    "objective": "Подобрать поездку",
    "steps": [
      {"action": "extract_trip_details", "reason": "Нормализовать запрос"},
      {"action": "validate_trip_details", "reason": "Проверить обязательные поля"},
      {"action": "determine_next_action", "reason": "Выбрать следующий шаг"},
      {"action": "negotiate_constraints", "reason": "Найти варианты"}
    ]
  },
  "tools_used": ["negotiate_constraints"],
  "tool_statuses": {"negotiate_constraints": "success"},
  "search_options": [],
  "redirect_url": null
}
```

При успешном поиске `search_options` содержит карточки, а не только текст агента. Основные поля
одной карточки:

| Поле | Назначение |
| --- | --- |
| `id` | ID candidate/journey для дальнейших операций |
| `kind` | `journey` или вариант с ослаблением `relaxation` |
| `title`, `explanation`, `changes[]` | готовое отображение результата и компромиссов |
| `total_price`, `currency` | итоговая цена варианта |
| `outbound`, `inbound`, `hotel` | полные выбранные компоненты JourneyOption |
| `action_url` | ссылка на следующий шаг/оформление |
| `tracking_payload` | готовый payload для запуска Price Intelligence без повторного parsing |
| `personalized`, `preference_score`, `preference_reasons` | результат Preference Learning |
| `rank_before`, `rank_after` | изменение позиции после персонализации |

`decision_intent` принимает значения `search`, `preferences`, `group_preferences`, `rescue`
или `what_if`. Для последних двух frontend после классификации вызывает соответствующий backend
фасад принятой поездки.

История:

```text
GET /api/v1/agent/users/{user_id}/sessions
GET /api/v1/agent/users/{user_id}/sessions/{session_id}
POST /api/v1/agent/users/{user_id}/sessions/{session_id}/documents/extract
```

### Принятая поездка, Rescue и What-if

```text
GET  /api/v1/trips/current
PUT  /api/v1/trips/current
POST /api/v1/trips/current/rescue
POST /api/v1/trips/current/what-if
```

`PUT /api/v1/trips/current` принимает исходный `TripSpec` и выбранный `JourneyOption`:

```json
{
  "trip": {
    "origin": "Москва",
    "destination": "Казань",
    "outbound_date": "2026-09-01",
    "return_date": "2026-09-05",
    "outbound_after": null,
    "return_before": null,
    "travelers": 1,
    "budget": 30000,
    "excluded_transport": [],
    "preferred_transport": ["train"],
    "max_transfers": 0,
    "hard_constraints": ["budget"]
  },
  "journey": {
    "id": "candidate-1",
    "total_price": 18900,
    "outbound": {
      "mode": "train",
      "origin": "Москва",
      "destination": "Казань",
      "departure": "2026-09-01T10:00:00+03:00",
      "arrival": "2026-09-01T21:00:00+03:00",
      "price": 9500,
      "currency": "RUB",
      "duration_minutes": 660,
      "transfers": 0,
      "carrier": null,
      "voyage_no": null,
      "booking_url": null
    },
    "inbound": {
      "mode": "train",
      "origin": "Казань",
      "destination": "Москва",
      "departure": "2026-09-05T18:00:00+03:00",
      "arrival": "2026-09-06T05:00:00+03:00",
      "price": 9400,
      "currency": "RUB",
      "duration_minutes": 660,
      "transfers": 0,
      "carrier": null,
      "voyage_no": null,
      "booking_url": null
    },
    "hotel": null
  }
}
```

Rescue и What-if принимают одинаковый компактный request:

```json
{"message": "Теперь нужно вернуться домой до 8 утра"}
```

Оба endpoint возвращают `{ "kind": "rescue|what_if", "result": {...} }` с candidates,
объяснениями, impact и обновлённым `TripSpec`. Rescue-кандидат можно применить повторным `PUT`.
What-if всегда является симуляцией и не меняет сохранённую поездку.

### Price Intelligence

```text
POST   /api/v1/tracker/trips
GET    /api/v1/tracker/trips/{tracking_id}
POST   /api/v1/tracker/trips/{tracking_id}/refresh
DELETE /api/v1/tracker/trips/{tracking_id}
```

Первичный ключ — не отдельный segment и не голый `candidate_id`. При создании backend передаёт
`tracking_payload` всей выбранной journey: `trip_spec` и ровно одну полную комбинацию
`journeys[0]` с outbound/inbound/hotel. Её `id` обычно совпадает с `SearchOption.id`. Tracker
возвращает собственный UUID в поле `id`; далее он используется как `tracking_id` для чтения,
refresh и остановки.

Основные поля ответа:

- `summary.current_price`, `minimum_price`, `average_price`, `difference_from_min`;
- `recommendation.status`: `COLLECTING_DATA`, `BUY_NOW`, `WAIT` или `GOOD_VALUE`;
- `recommendation.message` — готовое пользовательское объяснение;
- `current_trip` — фактически наблюдаемая комбинация;
- `history[]` — точки цены и score во времени;
- `active`, `created_at`, `last_checked_at`.

Отдельного числового `forecast` и `confidence` в текущем контракте нет. Inline-блок
`price_intelligence` в карточке — frontend-представление ответа tracker; он добавляется после
запуска проверки цены.

### Preferences и группы

```text
GET  /api/v1/preferences/cold-start/questions?limit=4
POST /api/v1/preferences/cold-start/complete
GET  /api/v1/preferences/me
POST /api/v1/preferences/group/profile
POST /api/v1/preferences/group/rerank
```

Личный `profile_id` всегда равен авторизованному `user_id` и не передаётся frontend отдельным
параметром в персональных endpoint. Для группы frontend передаёт `group_id` и
`participant_profile_ids`; backend автоматически добавляет профиль владельца группы.
Групповой профиль вычисляется отдельно и не перезаписывает личные preferences участников.

### Авторизация

```text
POST /api/v1/auth/code/request
POST /api/v1/auth/code/verify
POST /api/v1/auth/register
POST /api/v1/auth/password
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

Backend устанавливает подписанную HttpOnly cookie. При `AUTH_DEBUG=true` одноразовый код
возвращается в `debug_code`; в production этот режим должен быть выключен.

## Структура репозитория

```text
frontend/                    React 18 + TypeScript + Vite
backend/                     публичный FastAPI orchestrator и SQLite/Alembic
ai-service/                  stateless LangGraph agent
constraint-negotiator/       поиск и negotiation поверх Tutu MCP
smart-trip-tracker/backend/  Price Intelligence
trip-rescue/                 Rescue, What-if и Preference Intelligence
deploy/                      production Dockerfiles и Caddy
scripts/                     setup, dev, smoke, build, deploy и backup
compose.prod.yaml            production topology
DEPLOYMENT.md                эксплуатация и deployment
```

## Быстрый локальный запуск

Требования:

- Python 3.12+;
- Node.js и npm;
- `make`;
- доступ к OpenAI API и Tutu MCP.

Первичная установка создаёт локальные virtualenv, устанавливает Python/Node-зависимости и
применяет миграции:

```bash
make setup
```

Добавьте ключ только в игнорируемый корневой `.env`:

```dotenv
OPENAI_API_KEY=sk-...
```

Все сервисы умеют читать корневой `.env`; реальные ключи не нужно копировать в
`.env.example`. Файлы `.env`, `.env.*` и `.env.production` исключены из Git, кроме безопасных
example-файлов. Проверить перед коммитом:

```bash
git status --short
git check-ignore -v .env
```

Запуск всей цепочки:

```bash
make dev
```

| URL | Назначение |
| --- | --- |
| `http://127.0.0.1:5173` | приложение |
| `http://127.0.0.1:8000/docs` | публичный OpenAPI |
| `http://127.0.0.1:8000/health` | liveness backend |
| `http://127.0.0.1:8000/ready` | readiness публичной цепочки |

Логи каждого процесса находятся в `.local/logs`. Остановить всю цепочку можно `Ctrl+C` в
терминале с `make dev`.

### End-to-end smoke

В другом терминале:

```bash
make smoke
```

Smoke проходит через Vite proxy и публичный backend, вызывает реальный OpenAI API и Tutu MCP,
проверяет tool call Constraint Negotiator, карточки результатов и сохранение истории диалога.

## Проверки

Полный набор тестов:

```bash
make test
```

Отдельная сборка frontend и статические проверки backend:

```bash
cd frontend
npm run build
npm test

cd ../backend
.venv/bin/ruff check app tests
.venv/bin/python -m pytest -q
.venv/bin/alembic check
```

## Production

Production состоит из Caddy и пяти Python-контейнеров. Состояние хранится в отдельных volumes;
наружу публикуются только HTTP/HTTPS-порты Caddy.

```bash
cp .env.production.example .env.production
chmod 600 .env.production
make prod-deploy ENV_FILE=.env.production
```

Перед запуском задайте `AUTH_SECRET_KEY`, `AI_SERVICE_TOKEN`, `OPENAI_API_KEY`, домен и immutable
`IMAGE_TAG`. Подробные build/publish/deploy/backup/rollback инструкции находятся в
[DEPLOYMENT.md](DEPLOYMENT.md).

## Ограничения прототипа

- текущий backend использует SQLite и рассчитан на один экземпляр;
- хранится одна текущая принятая поездка на пользователя, без отдельного `trip_id`;
- Preference Store Trip Rescue пока файловый;
- доставка одноразового кода через email/SMS не подключена;
- точность и доступность вариантов зависят от OpenAI и внешнего Tutu MCP;
- перед публичным использованием необходимы полноценная авторизация доступа к истории,
  PostgreSQL, централизованные rate limits, мониторинг и внешний secret manager.

Проект является демонстрационным прототипом и не должен собирать данные сторонних аккаунтов или
использоваться как production booking system без отдельного security review.
