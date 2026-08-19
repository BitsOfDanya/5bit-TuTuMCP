# Smart Trip Tracker — isolated MVP

Отдельный прототип фичи Best Time to Book. Он не импортирует код основного
приложения и запускается на других портах.

## Что входит в минимальную версию

- структурированный TripIntent;
- перелёт туда-обратно + отель;
- публичный Tutu MCP adapter (Streamable HTTP, без авторизации);
- реальный поиск через Tutu MCP по умолчанию;
- воспроизводимый demo-provider для локальной работы без сети;
- ограниченный Trip Builder (до 5 перелётов × 5 отелей);
- детерминированный Trip Score;
- персистентная история snapshot в локальной SQLite;
- current/minimum/average;
- COLLECTING_DATA, BUY_NOW, WAIT, GOOD_VALUE;
- ручной реальный refresh;
- локальные сценарии падения на 7% и роста на 20% для проверки графика;
- остановка отслеживания без удаления накопленной истории;
- адаптивный React-интерфейс, подписанный SVG-график и история дельт.

## Запуск backend

    cd smart-trip-tracker/backend
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e '.[dev]'
    cp .env.example .env
    fastapi dev --port 8001

Документация API: http://127.0.0.1:8001/docs.

По умолчанию используется публичный Tutu MCP. Конфигурация `.env`:

    TRIP_PROVIDER=tutu
    TUTU_MCP_URL=https://mcp.tutu.ru/mcp

API-ключ для Tutu MCP не нужен. Актуальный endpoint:
https://mcp.tutu.ru/mcp.

Для полностью локальной работы без сетевых запросов установите
`TRIP_PROVIDER=demo`.

Путь к локальной базе можно изменить в `.env`:

    DATABASE_PATH=.data/smart-trip-tracker.db

## Запуск frontend

    cd smart-trip-tracker/frontend
    npm install
    npm run dev

Открыть http://127.0.0.1:5174.

## API

    POST   /api/v1/trips
    GET    /api/v1/trips
    GET    /api/v1/trips/{id}
    POST   /api/v1/trips/{id}/refresh
    POST   /api/v1/trips/{id}/simulate?scenario=drop|spike
    DELETE /api/v1/trips/{id}


## Как увидеть динамику

1. Создайте маршрут — это выполнит реальный поиск в Tutu MCP.
2. Нажмите «Цена снизилась на 7%» — появится новая точка и `BUY_NOW`.
3. Нажмите «Цена выросла на 20%» — график пойдёт вверх и появится `WAIT`.

Сценарии `drop` и `spike` не вызывают MCP и не подменяют реальный refresh.
Они воспроизводимо изменяют последнюю сохранённую цену. Ошибки валидации,
отсутствие подходящих комбинаций, остановленный трекинг и недоступность MCP
возвращаются как `422`, `409` и `502` и показываются в интерфейсе.
## Проверки

    cd smart-trip-tracker/backend
    .venv/bin/ruff check app tests
    .venv/bin/pytest

    cd ../frontend
    npm run build
    npm test

## Ограничения минимальной версии

- нет авторизации и пользовательской изоляции;
- нет scheduler и LLM explanation;
- пока поддерживается только round-trip avia + hotel;
- реальные предложения зависят от доступности публичного Tutu MCP.

Следующий этап: scheduler, уведомления, привязка к авторизации и интеграция
с основной страницей. При объединении можно заменить SQLite на PostgreSQL/Alembic.
