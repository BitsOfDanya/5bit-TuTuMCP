# Smart Trip Price Tracker / Best Time to Book

## 1. Цель фичи

Добавить в продукт функцию отслеживания стоимости **всей поездки**, а не только отдельного билета.

Поездка рассматривается как единая комбинация:

- транспорт туда;
- транспорт обратно;
- отель;
- даты;
- пользовательские ограничения;
- параметры качества поездки.

Система должна:

1. получать актуальные предложения через **Tutu MCP**;
2. собирать из них подходящие комбинации поездки;
3. сохранять стоимость лучшей подходящей комбинации во времени;
4. строить график изменения общей стоимости;
5. показывать текущую, минимальную и среднюю цену;
6. определять, выгодно ли покупать сейчас;
7. учитывать не только цену, но и качество текущей комбинации;
8. объяснять пользователю, почему сейчас стоит покупать или подождать.

Ключевая идея:

> Не просто найти минимальную цену, а определить лучший момент для покупки хорошей поездки.

---

# 2. Главный продуктовый тезис

Не:

> Мы отслеживаем цену конкретного билета.

А:

> Мы отслеживаем стоимость и качество лучшей поездки, подходящей под намерение пользователя.

Короткая формулировка:

> **Не "когда билет дешевле", а "когда поездку выгоднее купить".**

---

# 3. Источник данных

## Tutu MCP

Для получения актуальных данных по поездке использовать **Tutu MCP**.

Через MCP получать доступные инструменты поиска, например:

```text
search_trains(...)
search_flights(...)
search_hotels(...)
search_buses(...)
```

Точные имена инструментов должны соответствовать текущему MCP API проекта.

Не нужно делать отдельные парсеры или сторонние интеграции, если необходимые данные уже предоставляет Tutu MCP.

Основная схема:

```text
TripIntent
    ↓
Tutu MCP
    ↓
Raw offers
    ↓
Normalizer
    ↓
Trip Builder
    ↓
Ranking
    ↓
Best Offer
```

---

# 4. Роль LLM

LLM нужна, но **не должна быть ядром расчетов**.

## LLM использовать для

### 1. Разбора естественного запроса

Пользователь:

> Хочу с девушкой из Питера в Казань на выходные, до 35 тысяч, только не утром.

LLM превращает запрос в структурированный `TripIntent`:

```json
{
  "origin": "Санкт-Петербург",
  "destination": "Казань",
  "date_from": "2026-08-22",
  "date_to": "2026-08-24",
  "budget": 35000,
  "preferences": {
    "early_departure": false
  }
}
```

### 2. Человеческого explanation

Backend уже вычислил:

```json
{
  "current_price": 43600,
  "min_price": 42900,
  "difference_from_min": 700,
  "trip_score": 91,
  "previous_best_score": 71,
  "useful_time_gain_hours": 6
}
```

LLM может сформировать:

> Сейчас хороший момент для покупки. Цена всего на 700 ₽ выше недельного минимума, но текущая комбинация дает прямой маршрут и на 6 часов больше времени в городе.

---

## LLM НЕ использовать для

- расчета стоимости;
- сложения цен;
- процентов;
- min / max / average;
- определения Trip Score;
- хранения истории;
- поиска текущего минимума;
- rule-based recommendation;
- принятия критичных решений без структурированных данных.

Все эти операции делать обычным backend-кодом.

---

# 5. Базовая архитектура

```text
Пользователь
    ↓
Frontend
    ↓
Backend API
    ↓
TripIntent / TripSpec
    ↓
Tutu MCP
    ↓
Normalizer
    ↓
Trip Builder
    ↓
Ranking Engine
    ↓
Best Offer Snapshot
    ↓
PostgreSQL
    ↓
Recommendation Engine
    ↓
Frontend
```

LLM находится сбоку:

```text
User text
   ↓
LLM
   ↓
TripIntent
```

и:

```text
Structured recommendation
   ↓
LLM
   ↓
Human-readable explanation
```

---

# 6. Что именно отслеживаем

Есть два возможных подхода.

## Вариант A — конкретную комбинацию

Например:

```text
конкретный авиарейс
+
конкретный поезд обратно
+
конкретный Hotel X
```

Плюсы:

- просто реализовать;
- легко сравнивать цену одной и той же комбинации.

Минусы:

- билет может исчезнуть;
- рейс может перестать быть доступен;
- отель может закончиться;
- можно пропустить более выгодную новую комбинацию.

---

## Вариант B — намерение пользователя

Например:

```text
СПб → Казань
23–25 августа
до 40 000 ₽
без пересадок
не раньше 10:00
отель rating >= 8
```

Каждый refresh система снова ищет варианты через MCP и выбирает лучшую комбинацию под эти условия.

Плюсы:

- система всегда ищет лучший актуальный вариант;
- может обнаружить новую комбинацию;
- лучше соответствует идее AI travel agent.

Минусы:

- сложнее сравнивать разные комбинации;
- нужен ranking и Trip Score.

---

# 7. Рекомендуемая реализация: гибрид

Для хакатона использовать:

```text
TripIntent
+
BestOfferSnapshot
```

## TripIntent

Хранит стабильное намерение пользователя:

```text
origin
destination
dates
budget
transport preferences
hotel preferences
time preferences
other constraints
```

## BestOfferSnapshot

Хранит лучший найденный вариант в конкретный момент времени:

```text
timestamp
total_price
selected_transport
selected_hotel
trip_score
useful_time
transfers
quality metrics
```

Таким образом график показывает:

> **Сколько стоила лучшая поездка, подходящая этому пользователю, в разные моменты времени.**

Это предпочтительнее, чем отслеживать один конкретный билет.

---

# 8. Основной workflow отслеживания

## Первый поиск

```text
TripIntent
    ↓
Tutu MCP
    ↓
N транспортных предложений
+
M отелей
    ↓
Normalizer
    ↓
Trip Builder
    ↓
Ranking
    ↓
Best combination
    ↓
BestOfferSnapshot #1
```

Например:

```text
12:00
Best trip: 39 000 ₽
Trip Score: 84
```

---

## Повторный поиск

Через заданный интервал:

```text
TripIntent
    ↓
Tutu MCP
    ↓
Новые актуальные предложения
    ↓
Normalizer
    ↓
Trip Builder
    ↓
Ranking
    ↓
Новая best combination
    ↓
BestOfferSnapshot #2
```

Например:

```text
13:00
Best trip: 37 500 ₽
Trip Score: 86
```

---

## История

```text
12:00 → 39 000 ₽
13:00 → 37 500 ₽
14:00 → 38 200 ₽
15:00 → 36 900 ₽
```

На основе этого строится график.

---

# 9. Пользовательский сценарий

### Шаг 1

Пользователь вводит:

> Москва → Казань, 23–25 августа, до 30 000 ₽, без ранних выездов.

### Шаг 2

LLM или обычная форма формирует TripIntent.

### Шаг 3

Backend вызывает Tutu MCP.

### Шаг 4

Полученные предложения нормализуются.

### Шаг 5

Trip Builder собирает возможные комбинации:

```text
transport outbound
+
transport inbound
+
hotel
```

### Шаг 6

Ranking Engine выбирает лучшую комбинацию.

### Шаг 7

Пользователь нажимает:

**Следить за поездкой**

### Шаг 8

Создается `TripTracking`.

### Шаг 9

Через некоторое время выполняется новый поиск по тому же `TripIntent`.

### Шаг 10

Новый лучший вариант сохраняется как следующий snapshot.

---

# 10. Data Model

## TripTracking

```text
id
user_id
trip_intent
created_at
active
last_checked_at
```

`trip_intent` можно хранить JSONB для MVP.

Пример:

```json
{
  "origin": "Санкт-Петербург",
  "destination": "Казань",
  "date_from": "2026-08-23",
  "date_to": "2026-08-25",
  "budget": 40000,
  "preferences": {
    "direct_only": true,
    "departure_after": "10:00",
    "hotel_rating_min": 8
  }
}
```

---

## BestOfferSnapshot

```text
id
tracking_id
timestamp

total_price

transport_price
hotel_price
extra_price

trip_score
travel_time_minutes
useful_time_hours
transfers
hotel_rating

offer_snapshot
```

`offer_snapshot` можно хранить JSONB.

---

# 11. Пример snapshot

```json
{
  "tracking_id": "trip_123",
  "timestamp": "2026-08-19T12:00:00",
  "total_price": 43600,
  "components": {
    "transport": 21800,
    "hotel": 19800,
    "extras": 2000
  },
  "metrics": {
    "trip_score": 0.91,
    "travel_time_minutes": 610,
    "useful_time_hours": 31,
    "transfers": 0,
    "hotel_rating": 8.8
  },
  "offer_snapshot": {
    "outbound_offer_id": "flight_123",
    "inbound_offer_id": "train_456",
    "hotel_offer_id": "hotel_789"
  }
}
```

---

# 12. Normalizer

MCP может возвращать разные структуры для поездов, самолетов и отелей.

Перед ranking привести данные к единому внутреннему формату.

Пример транспорта:

```json
{
  "id": "offer_123",
  "type": "flight",
  "price": 8200,
  "departure_at": "2026-08-23T13:20:00",
  "arrival_at": "2026-08-23T15:00:00",
  "duration_minutes": 100,
  "transfers": 0,
  "provider": "tutu",
  "raw": {}
}
```

Пример отеля:

```json
{
  "id": "hotel_123",
  "price_total": 18000,
  "rating": 8.8,
  "distance_to_center_km": 1.4,
  "provider": "tutu",
  "raw": {}
}
```

Для production `raw` можно не сохранять целиком.

---

# 13. Trip Builder

Trip Builder получает нормализованные предложения и формирует возможные комбинации.

Минимальная комбинация:

```text
outbound transport
+
inbound transport
+
hotel
```

Пример:

```json
{
  "outbound": {},
  "inbound": {},
  "hotel": {},
  "total_price": 32600,
  "metrics": {}
}
```

Для хакатона не нужно генерировать полный декартов продукт из тысяч предложений.

Можно:

1. взять TOP-N транспорта туда;
2. TOP-N обратно;
3. TOP-N отелей;
4. собрать ограниченное число комбинаций;
5. посчитать score;
6. выбрать лучшие.

Например `N = 5–10`.

---

# 14. Trip Score

Trip Score считать кодом, без LLM.

Пример:

```text
trip_score =
    price_score * 0.30 +
    travel_time_score * 0.20 +
    useful_time_score * 0.20 +
    comfort_score * 0.10 +
    hotel_score * 0.10 +
    preferences_score * 0.10
```

Все показатели нормализовать в диапазон `0..1`.

Trip Score нужен для сравнения разных комбинаций между собой.

---

# 15. Useful Time

Дополнительная важная метрика:

> сколько полезного времени пользователь реально проведет в пункте назначения.

Упрощенная формула:

```text
useful_time =
departure_back -
arrival_outbound
```

В более продвинутой версии можно учитывать:

- время до аэропорта;
- ожидание;
- багаж;
- трансферы;
- заселение в отель.

Для MVP достаточно надежной упрощенной метрики.

---

# 16. Recommendation Engine

Recommendation Engine должен быть детерминированным.

Рассчитываем:

```text
current_price
min_price
max_price
avg_price
price_delta_from_min
price_delta_from_avg
price_change_1d
price_change_3d
current_trip_score
best_historical_trip_score
```

Статусы:

```text
BUY_NOW
WAIT
PRICE_RISING
GOOD_VALUE
```

---

## BUY_NOW

Если:

```text
current_price <= min_price * 1.03
```

Ответ:

> Цена близка к наблюдаемому минимуму.

---

## GOOD_VALUE

Если:

```text
current_price < avg_price * 0.93
```

Ответ:

> Цена заметно ниже средней.

---

## WAIT

Если:

```text
current_price > min_price * 1.10
```

и нет устойчивого роста:

> Текущая цена заметно выше недавнего минимума.

---

## PRICE_RISING

Если цена растет несколько snapshot подряд:

> Цена растет. Если текущий вариант подходит, есть риск дальнейшего роста.

---

# 17. Главное отличие от простого price tracker

Нельзя сравнивать только цену.

Пример:

### 15 августа

```text
Цена: 42 000 ₽
Trip Score: 71
```

Но:

- пересадка;
- неудобное время;
- меньше времени в городе.

### 19 августа

```text
Цена: 43 600 ₽
Trip Score: 91
```

Текущий вариант дороже на 1 600 ₽, но существенно лучше.

Система должна уметь вернуть:

> Самая низкая цена была 15 августа, но лучший вариант доступен сейчас.

> Доплата 1 600 ₽ дает прямой маршрут, более удобное время и +6 часов в городе.

Это основной WOW-сценарий.

---

# 18. График

Frontend должен отображать линейный график полной стоимости лучшей подходящей поездки.

Показывать:

- историю цены;
- текущую цену;
- минимум;
- среднее значение;
- tooltip;
- текущий recommendation.

Пример:

```text
Стоимость поездки

49k │ ●
    │  ╲
47k │   ●
    │    ╲
45k │     ●       ●
    │      ╲     ╱ ╲
43k │       ●───●   ● ← сейчас 43 600 ₽
    │       ↑
42k │   минимум 42 900 ₽
    └────────────────────
      13  14  15  16  17  18  19 авг
```

---

# 19. Backend API

## Создать tracking

```http
POST /api/trips/track
```

Body:

```json
{
  "trip_intent": {}
}
```

Backend:

1. валидирует TripIntent;
2. делает первый MCP search;
3. выбирает best offer;
4. создает tracking;
5. сохраняет snapshot.

---

## История

```http
GET /api/trips/{tracking_id}/history
```

Response:

```json
{
  "current_price": 43600,
  "min_price": 42900,
  "avg_price": 44850,
  "recommendation": "BUY_NOW",
  "history": []
}
```

---

## Refresh

```http
POST /api/trips/{tracking_id}/refresh
```

Backend:

```text
load TripIntent
→ call Tutu MCP
→ normalize
→ build trips
→ rank
→ save BestOfferSnapshot
→ recalculate recommendation
```

---

## Stop tracking

```http
DELETE /api/trips/{tracking_id}/track
```

---

# 20. MCP service layer

Желательно вынести взаимодействие с MCP в отдельный сервис.

Например:

```text
backend/app/services/tutu_mcp.py
```

Интерфейс:

```python
async def search_transport(trip_intent):
    ...

async def search_hotels(trip_intent):
    ...

async def search_trip_candidates(trip_intent):
    ...
```

Остальной backend не должен зависеть от raw MCP response.

---

# 21. Recommendation response

Backend возвращает structured result.

```json
{
  "status": "BUY_NOW",
  "confidence": 0.84,
  "current_price": 43600,
  "minimum_price": 42900,
  "average_price": 44850,
  "difference_from_min": 700,
  "difference_from_min_percent": 1.63,
  "current_trip_score": 91,
  "best_price_trip_score": 71,
  "message_code": "NEAR_MIN_BETTER_QUALITY"
}
```

Если есть LLM layer, она получает именно этот объект и формирует текст.

---

# 22. LLM API abstraction

Не привязывать бизнес-логику к конкретной модели.

Создать abstraction:

```python
class LLMService:
    async def parse_trip_intent(self, user_text: str) -> TripIntent:
        ...

    async def explain_recommendation(self, data: RecommendationData) -> str:
        ...
```

Можно использовать OpenAI, другой model API или локальную модель.

При недоступности LLM основная price tracking фича должна продолжать работать.

---

# 23. Hidden Costs

P1/P2.

Если данные доступны, дополнительно учитывать:

- багаж;
- трансфер до аэропорта;
- трансфер от аэропорта;
- дополнительные ночи;
- дополнительные пересадки.

Пример:

```text
Самолет:
7 000 билет
2 000 багаж
1 500 трансферы
= 10 500 ₽

Поезд:
8 200 ₽
= 8 200 ₽
```

Не делать это обязательным для P0, если MCP не предоставляет надежные данные.

---

# 24. Demo Mode

Для хакатона не нужно ждать несколько часов/дней.

Добавить:

```http
POST /api/trips/{tracking_id}/simulate
```

или debug-кнопку:

```text
Simulate next check
```

Варианты реализации:

### Вариант 1

Повторно вызвать MCP и сохранить новую реальную цену.

### Вариант 2

Если цены не изменились, в demo mode использовать заранее подготовленные mock snapshots.

Пример:

```text
46 800 ₽
44 200 ₽
42 900 ₽
43 600 ₽
```

Важно визуально показать работу графика и recommendation engine.

---

# 25. Scheduler

Для реальной версии:

```text
scheduler
   ↓
active TripTracking
   ↓
Tutu MCP refresh
   ↓
new snapshot
```

Для хакатона полноценный scheduler необязателен.

P0:

```text
manual refresh / simulate
```

P2:

```text
background scheduler every N hours
```

---

# 26. MVP Priority

## P0 — обязательно

- TripIntent;
- интеграция с Tutu MCP;
- Normalizer;
- Trip Builder;
- простой Ranking;
- TripTracking;
- BestOfferSnapshot;
- history endpoint;
- line chart;
- current/min/average price;
- BUY_NOW / WAIT;
- кнопка "Следить за поездкой";
- ручной refresh;
- demo/simulate.

## P1 — желательно

- Trip Score;
- Useful Time;
- сравнение качества исторических комбинаций;
- LLM explanation;
- статус PRICE_RISING / GOOD_VALUE.

## P2 — если останется время

- background scheduler;
- notifications;
- hidden costs;
- personalized ranking;
- Telegram / push notifications;
- forecasting.

---

# 27. Что НЕ делать

Для MVP не нужно:

- обучать ML-модель прогнозирования цен;
- строить time-series forecasting;
- пытаться предсказать точную будущую стоимость;
- отдавать арифметику LLM;
- хранить гигантские raw MCP responses;
- строить десятки агентов;
- делать отдельные сторонние парсеры, если данные доступны через Tutu MCP.

---

# 28. Рекомендуемая структура модулей

Пример:

```text
backend/app/

schemas.py
models.py

services/
    tutu_mcp.py
    trip_normalizer.py
    trip_builder.py
    trip_ranker.py
    trip_tracker.py
    recommendation.py
    llm.py

api/
    trip_tracking.py
```

Разделение ответственности:

```text
tutu_mcp
→ только получение данных

trip_normalizer
→ raw MCP → internal models

trip_builder
→ создание комбинаций

trip_ranker
→ score + выбор лучших

trip_tracker
→ tracking + snapshots

recommendation
→ BUY_NOW / WAIT / etc

llm
→ parsing + explanation
```

---

# 29. Главный end-to-end flow

```text
User:
"Хочу в Казань на выходные до 40к"

        ↓

LLM / parser

        ↓

TripIntent

        ↓

Tutu MCP

        ↓

Transport + hotels

        ↓

Normalizer

        ↓

Trip Builder

        ↓

Ranking Engine

        ↓

Best Trip

        ↓

BestOfferSnapshot

        ↓

Database

        ↓

History + Recommendation

        ↓

Frontend graph

        ↓

"Хороший момент для покупки"
```

Через некоторое время:

```text
same TripIntent
        ↓
new MCP search
        ↓
new best trip
        ↓
new snapshot
        ↓
graph update
        ↓
new recommendation
```

---

# 30. Definition of Done

Фича считается готовой, если:

1. Пользователь может сформировать TripIntent.
2. Backend умеет получить актуальные предложения через Tutu MCP.
3. MCP responses нормализуются во внутренние структуры.
4. Из предложений собирается хотя бы одна валидная trip combination.
5. Ranking выбирает best combination.
6. Пользователь может включить tracking.
7. Backend сохраняет минимум два BestOfferSnapshot для одного TripIntent.
8. Frontend отображает историю цены на line chart.
9. Показываются current / min / average.
10. Recommendation Engine возвращает хотя бы BUY_NOW / WAIT.
11. Можно вручную вызвать refresh.
12. Есть demo/simulate режим.
13. Желательно считается Trip Score.
14. Желательно LLM формирует explanation из structured recommendation.
15. В demo можно показать ситуацию, когда самая дешевая историческая комбинация не является лучшей по Trip Score.

---

# 31. Ключевая идея для Codex

При реализации считать основным объектом не конкретный билет, а:

```text
TripIntent
```

То есть неизменное намерение пользователя.

Каждый refresh:

```text
TripIntent
→ Tutu MCP
→ новые предложения
→ ranking
→ BestOfferSnapshot
```

Поэтому график отображает изменение стоимости **лучшей подходящей поездки во времени**, а не изменение цены одного конкретного рейса.

Это центральная архитектурная идея фичи.
