# Trip Rescue

Trip Rescue — decision layer для уже выбранной поездки.

Сервис не строит путешествие заново при каждом изменении планов. Он принимает текущий `TripSpec`, уже выбранный `JourneyOption` и новое сообщение пользователя, определяет, какая часть поездки перестала подходить, сохраняет всё ещё валидное и через Tutu MCP ищет минимальную замену.

Помимо rescue flow сервис содержит decision intelligence вокруг уже найденных поездок: Negotiation Fallback, Journey Intelligence, Preference Learning, Preference Cold Start, Group Preferences, What-if Simulation и Decision Explanation.

Основная идея:

> Обычный поиск строит поездку с нуля. Trip Rescue понимает уже принятое решение и старается изменить в нём как можно меньше.

---

## Возможности

Trip Rescue умеет:

- понимать изменения поездки из естественного языка;
- определять изменившиеся ограничения;
- разделять hard и soft constraints;
- детерминированно защищать hard constraints после LLM parsing;
- определять сломанную часть существующей поездки;
- сохранять валидные части Journey;
- искать только необходимые replacement components;
- использовать реальные предложения Tutu через MCP;
- искать обратный транспорт в предыдущий календарный день, если это требуется deadline прибытия;
- проверять полную feasibility после merge;
- ранжировать варианты по минимальности изменений;
- находить ближайшие компромиссы, если exact-варианта нет;
- никогда не ослаблять hard constraints в Negotiation Fallback;
- определять потенциально ненужные ночи отеля;
- строить Decision Explanation;
- запускать What-if Simulation без изменения принятой поездки;
- обучаться на `like / dislike / choose / reject`;
- персонализировать ranking;
- проводить Preference Cold Start через pairwise choices;
- объединять индивидуальные preference profiles для групповой поездки;
- вычислять group consensus/conflicts;
- хранить preference profiles между перезапусками;
- работать с Tutu MCP;
- работать в Docker.

---

## Архитектура Rescue

```text
User update
    │
    ▼
AI Trip Update Parser
    │
    ▼
Deterministic Semantic Hardening
    │
    ▼
Updated TripSpec
    │
    ▼
Trip Diff
    │
    ▼
Breakage Detection
    │
    ├── preserve valid components
    │
    └── replace invalid components
            │
            ▼
       Rescue Planner
            │
            ▼
       Tutu MCP Search
            │
            ▼
       Candidate Merge
            │
            ▼
   Deterministic Feasibility
            │
      ┌─────┴─────┐
      ▼           ▼
    exact      no exact
      │           │
      │           ▼
      │     negotiation fallback
      │           │
      │      soft relaxations
      │           │
      └─────┬─────┘
            ▼
    Journey Intelligence
            │
            ▼
      Base Rescue Ranking
            │
            ▼
     Preference Reranking
            │
            ▼
    Decision Explanation
            │
            ▼
        Public API
```

---

## Ключевой принцип

LLM не принимает критические решения о валидности поездки.

LLM используется для parsing естественного языка и понимания того, какие поля изменил пользователь.

Детерминированный Python-код отвечает за:

- применение `TripSpec` patch;
- hard/soft semantics;
- feasibility;
- component preservation;
- relaxation policy;
- candidate merge;
- ranking;
- What-if impact calculation;
- preference scoring;
- group aggregation;
- validation.

---

# Core Rescue

## Hard constraints

Поддерживаются:

```text
budget
outbound_after
return_before
transport
max_transfers
```

Например:

```text
23 августа мне обязательно нужно быть в Москве до 8 утра
```

превращается в:

```json
{
  "return_before": "08:00:00",
  "hard_constraints": ["return_before"]
}
```

После semantic hardening этот hard constraint не может быть ослаблен Negotiation Fallback.

## Soft constraints

Например:

```text
желательно уложиться в 10 тысяч
```

может дать `budget = 10000` без `budget` в `hard_constraints`.

Если exact-варианта нет, система может предложить минимальное увеличение бюджета.

## Minimal Replanning

```text
Москва → Казань
автобус
+
отель
+
Казань → Москва
самолёт, прибытие 08:40
```

После сообщения:

```text
Теперь обязательно нужно быть в Москве до 8 утра
```

Trip Rescue определяет:

```text
outbound  -> valid   -> preserve
hotel     -> valid   -> preserve
inbound   -> invalid -> replace
```

И выполняет поиск только обратной дороги.

## Negotiation Fallback

Если exact candidate отсутствует, сервис ищет ближайшие допустимые компромиссы только по soft constraints.

Пример:

```text
HARD:
вернуться до 08:00

SOFT:
бюджет <= 10 000 ₽
```

Если маршрут стоит дороже:

```json
{
  "status": "negotiation_required",
  "relaxations": [
    {
      "field": "budget",
      "old_value": 10000,
      "new_value": 17409
    }
  ]
}
```

`return_before = 08:00` остаётся неизменным.

---

# Journey Intelligence

После replanning сервис анализирует побочные эффекты.

Пример:

```json
{
  "type": "hotel_unused_nights",
  "severity": "warning",
  "action": "search_shorter_hotel",
  "estimated_amount": 3275,
  "estimated_unused_nights": 1
}
```

Это позволяет показать потенциальную дополнительную экономию после изменения маршрута.

---

# Decision Explanation

Rescue и What-if candidates получают структурированное объяснение решения.

```json
{
  "headline": "Меняем только дорогу обратно",
  "summary": "Сохраняем дорогу туда и отель. Меняем дорогу обратно. Экономия 5 294 ₽.",
  "reasons": [
    {
      "type": "preservation",
      "text": "Сохраняем дорогу туда и отель.",
      "positive": true
    }
  ],
  "tradeoffs": [],
  "preserved_components": ["outbound", "hotel"],
  "changed_components": ["inbound"]
}
```

Explanation строится на уже рассчитанных facts и не меняет решение.

---

# What-if Simulation

What-if отвечает на вопрос:

> Что будет, если изменить условие, но пока не менять принятую поездку?

Семантика:

```text
Rescue:
планы реально поменялись
-> строим replacement

What-if:
пользователь только сравнивает сценарий
-> accepted trip не мутируется
```

Endpoints:

```http
POST /api/v1/what-if/from-text
POST /api/v1/what-if/from-text/public
POST /api/v1/what-if/from-spec
POST /api/v1/what-if/from-spec/public
```

Statuses:

```text
no_difference
alternatives_found
negotiation_required
no_alternatives
```

Пример impact:

```json
{
  "price_delta": -5294,
  "savings": 5294,
  "price_change_percent": -23.32,
  "inbound_arrival_delta_minutes": -160,
  "components_changed": ["inbound"],
  "components_preserved": ["outbound", "hotel"],
  "disruption_count": 1
}
```

What-if возвращает ranked alternatives и Decision Explanation, но не изменяет текущую поездку.

---

# Preference Learning

Сигналы:

```text
like
dislike
choose
reject
```

Могут обучаться:

```text
transport affinity
price sensitivity
duration sensitivity
transfer sensitivity
hotel quality sensitivity
```

Preference Learning влияет только на ranking уже допустимых вариантов.

Feasibility и hard constraints от preferences не зависят.

## Preference API

```http
POST   /api/v1/preferences/feedback
GET    /api/v1/preferences/{profile_id}
DELETE /api/v1/preferences/{profile_id}
POST   /api/v1/preferences/rerank
```

При `choose` желательно передавать все варианты, которые видел пользователь, чтобы обучать pairwise preferences.

---

# Preference Cold Start

Cold Start позволяет начать personalization до накопления истории.

Endpoints:

```http
GET  /api/v1/preferences/cold-start/questions
POST /api/v1/preferences/cold-start/complete
```

После прохождения профиль продолжает обновляться обычными feedback events.

---

# Group Preferences

Group Preferences объединяет несколько индивидуальных preference profiles во временный виртуальный профиль группы.

Индивидуальные профили остаются source of truth, виртуальный group profile отдельно не сохраняется.

```text
profile A ─┐
           │
profile B ─┼─> group aggregation
           │          │
profile C ─┘          ▼
               virtual group profile
                       │
                       ▼
               existing reranking
```

Endpoints:

```http
POST /api/v1/preferences/group/profile
POST /api/v1/preferences/group/rerank
```

Group response может содержать:

```text
consensus_score
conflicts
highlights
```

Для UI `consensus_score` лучше интерпретировать как уровень согласованности, а не как процент одинаковых предпочтений.

---

# Preference persistence

Локально:

```text
./data/preferences.json
```

В Docker:

```text
/data/preferences.json
```

Persistent volume:

```text
trip-rescue-data
```

---

# API

Base URL:

```text
http://127.0.0.1:8020
```

Swagger:

```text
/docs
```

OpenAPI:

```text
/openapi.json
```

## Health

```http
GET /health
```

```json
{
  "status": "ok",
  "service": "trip-rescue",
  "version": "0.2.0"
}
```

## Readiness

```http
GET /ready
```

## MCP diagnostics

```http
GET /api/v1/system/mcp
GET /api/v1/system/mcp?refresh=true
```

## Metrics

```http
GET /api/v1/system/metrics
```

---

# Rescue API

Основной public endpoint:

```http
POST /api/v1/rescue/from-text/public
```

Пример:

```json
{
  "current_trip": {
    "origin": "Москва",
    "destination": "Казань",
    "outbound_date": "2026-08-21",
    "return_date": "2026-08-23",
    "outbound_after": "19:00:00",
    "return_before": "22:00:00",
    "travelers": 2,
    "budget": 22703,
    "excluded_transport": [],
    "preferred_transport": [],
    "max_transfers": null,
    "hard_constraints": []
  },
  "current_journey": {
    "id": "accepted-trip",
    "total_price": 22703,
    "outbound": {},
    "inbound": {},
    "hotel": {}
  },
  "message": "Теперь обязательно нужно быть в Москве до 8 утра",
  "reference_date": "2026-08-19",
  "preference_profile_id": "user-123"
}
```

`preference_profile_id` optional.

## Rescue statuses

```text
no_change
candidates_found
negotiation_required
no_candidates
```

## Other Rescue endpoints

```http
POST /api/v1/rescue/from-text
POST /api/v1/rescue/from-spec
POST /api/v1/rescue/from-spec/public
POST /api/v1/rescue/parse-update
```

---

# Tutu MCP

Trip Rescue использует Tutu MCP как источник реальных travel offers.

В текущей интеграции доступно 16 MCP tools.

Transport/hotel normalizers сохраняют Tutu metadata, включая `checkout_ref`, во внутренних `JourneyOption`.

---

# Установка

```text
Python 3.12
Docker
Docker Compose
```

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
```

---

# Environment

Создать `.env` на основе `.env.example`.

```env
PREFERENCE_STORE_PATH=./data/preferences.json
```

Docker Compose использует `/data/preferences.json`.

Секреты не должны попадать в git.

---

# Local run

```bash
python -m uvicorn app.main:app   --host 0.0.0.0   --port 8020
```

---

# Tests

```bash
python -m pytest -q
```

Текущее regression состояние:

```text
115 passed
```

Дополнительные suites:

```bash
python -m pytest tests/test_parser_hardening.py -q
python -m pytest tests/test_whatif.py tests/test_whatif_api.py -q
```

Cold Start:

```text
tests/test_preference_cold_start.py
tests/test_preference_cold_start_api.py
```

Group Preferences:

```text
tests/test_group_preferences.py
tests/test_group_preferences_api.py
```

---

# End-to-end smoke

Полный suite:

```bash
make smoke
```

Включает:

```text
smoke-rescue
smoke-fallback
smoke-preferences
smoke-group-preferences
smoke-whatif
```

Отдельно:

```bash
python -m scripts.smoke_rescue
python -m scripts.smoke_fallback
python -m scripts.smoke_preferences
python -m scripts.smoke_group_preferences
python -m scripts.smoke_whatif
```

Ожидаемые финалы:

```text
TRIP RESCUE END-TO-END: OK
NEGOTIATION FALLBACK: OK
PREFERENCE LEARNING END-TO-END: OK
GROUP PREFERENCES END-TO-END: OK
WHAT-IF SIMULATION: OK
```

Production smoke:

```bash
make smoke-prod
```

Ожидаемый финал:

```text
PRODUCTION SMOKE: OK
```

---

# Docker

```bash
docker compose build
docker compose up -d
docker compose ps
```

Logs:

```bash
docker compose logs   --tail=100   trip-rescue
```

Stop:

```bash
docker compose down
```

---

# Makefile

Основные команды:

```text
make test
make test-hardening
make test-whatif

make smoke
make smoke-rescue
make smoke-fallback
make smoke-preferences
make smoke-group-preferences
make smoke-whatif
make smoke-prod

make build
make up
make down
make rebuild
make logs
make ps
make health
make mcp
make openapi
```

---

# Integration

Trip Rescue — самостоятельный decision service.

Для AI-agent:

```http
POST /api/v1/rescue/from-text/public
```

Если внешний Agent уже построил новый `TripSpec`:

```http
POST /api/v1/rescue/from-spec/public
```

Preference feedback отправляется после пользовательских действий отдельным запросом.

What-if используется для hypothetical comparison и не должен мутировать принятую поездку.

Канонические объекты:

```text
TripSpec
JourneyOption
```

---

# Связь с Constraint Negotiator

Constraint Negotiator отвечает за первоначальный поиск:

```text
new request
   ↓
TripSpec
   ↓
JourneyOption candidates
```

Trip Rescue отвечает за изменение уже выбранного решения:

```text
accepted TripSpec
+
accepted JourneyOption
+
new user constraint
   ↓
minimal replacement
```

What-if использует тот же контекст, но только моделирует альтернативный сценарий.

---

# Service

```text
name: trip-rescue
version: 0.2.0
default port: 8020
tests: 115 passed
```
