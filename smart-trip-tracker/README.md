# Smart Trip Tracker — isolated MVP

Отдельный прототип фичи Best Time to Book. Он не импортирует код основного
приложения и запускается на других портах.

## Что входит в минимальную версию

- вход в формате PublicNegotiationResult сервиса constraint-negotiator;
- импорт транспорта туда-обратно и опционального отеля;
- поддержка статусов success и negotiation_required;
- повторный импорт того же формата как новой точки истории;
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

## Связка с Constraint Negotiator

1. Получите результат из одного из публичных endpoint:

       POST http://127.0.0.1:8010/api/v1/negotiator/from-text/public
       POST http://127.0.0.1:8010/api/v1/negotiator/from-spec/public

2. Передайте полученный JSON без преобразований:

       POST http://127.0.0.1:8001/api/v1/trips

   Для success выбирается самая дешёвая поездка из journeys. Для
   negotiation_required выбирается альтернатива с минимальным score, а её
   new_trip_spec становится параметрами отслеживания.

3. Для новой реальной точки повторите поиск в Constraint Negotiator:

       POST http://127.0.0.1:8001/api/v1/trips/{tracking_id}/observations

Результат no_options не создаёт отслеживание и возвращает 422.


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
    POST   /api/v1/trips/{id}/observations
    POST   /api/v1/trips/{id}/simulate?scenario=drop|spike
    DELETE /api/v1/trips/{id}


## Как увидеть динамику

1. Вставьте JSON результата Constraint Negotiator и создайте отслеживание.
2. Вставьте результат повторного поиска и нажмите «Добавить как новую точку».
3. Для демонстрации используйте кнопки падения или роста цены.

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
- поддерживается round-trip транспорт, отель опционален;
- реальные предложения формирует Constraint Negotiator через Tutu MCP.

Следующий этап: scheduler, уведомления, привязка к авторизации и интеграция
с основной страницей. При объединении можно заменить SQLite на PostgreSQL/Alembic.
