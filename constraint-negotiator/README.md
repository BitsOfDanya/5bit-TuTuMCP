

Constraint Negotiator — decision service для поиска поездок по пользовательским ограничениям поверх Tutu MCP.

Сервис принимает запрос пользователя в естественном языке или готовый `TripSpec`, получает реальные travel offers через Tutu MCP, проверяет их по ограничениям и либо возвращает подходящие `JourneyOption`, либо предлагает минимальные допустимые компромиссы.

Основная идея:

> Обычный поиск отвечает на вопрос «что найдено». Constraint Negotiator отвечает на вопрос «что реально подходит пользователю и чем минимально можно пожертвовать, если идеального варианта нет».

---

## Возможности

Constraint Negotiator умеет:

- преобразовывать естественный язык в канонический `TripSpec`;
- различать hard и soft constraints;
- не ослаблять hard constraints при поиске компромиссов;
- принимать готовый `TripSpec` без вызова LLM;
- искать реальные авиа-, ж/д-, автобусные, пригородные и hotel offers через Tutu MCP;
- собирать полные `JourneyOption`;
- проверять feasibility детерминированным кодом;
- находить ближайшие alternatives, если exact-варианта нет;
- предпочитать минимальные изменения условий;
- возвращать frontend-friendly public response;
- сохранять внутренние Tutu metadata для дальнейшего checkout;
- создавать реальный checkout handoff через `create_checkout_link`;
- работать без `OPENAI_API_KEY` для deterministic endpoints;
- отдавать health/readiness/MCP diagnostics/metrics;
- работать в Docker.

---

## Архитектура

```text
Natural language
      │
      ▼
AI Trip Parser
      │
      ▼
   TripSpec
      │
      ├─────────────────────────────┐
      │                             │
      │                    ready TripSpec
      │                             │
      └──────────────┬──────────────┘
                     ▼
              LangGraph flow
                     │
                     ▼
                Tutu MCP
                     │
                     ▼
             JourneyOption[]
                     │
                     ▼
          Deterministic Feasibility
                     │
             ┌───────┴────────┐
             │                │
             ▼                ▼
        exact match      no exact match
             │                │
             │                ▼
             │       Relaxation / Negotiation
             │                │
             └───────┬────────┘
                     ▼
                Public API
                     │
                     ▼
              selected option
                     │
                     ▼
          Tutu checkout handoff
```

---

## Ключевой принцип

LLM не принимает критические решения о валидности поездки.

LLM используется для:

- parsing естественного языка;
- извлечения структуры поездки;
- определения явно заданных hard constraints.

Детерминированный Python-код отвечает за:

- validation `TripSpec`;
- feasibility;
- hard/soft semantics;
- поиск допустимых relaxations;
- ranking alternatives;
- сохранение hard constraints;
- подготовку итогового результата.

Если главный AI-agent уже сформировал `TripSpec`, LLM внутри Constraint Negotiator вообще не нужен.

---

## Канонический TripSpec

```json
{
  "origin": "Москва",
  "destination": "Казань",
  "outbound_date": "2026-08-21",
  "return_date": "2026-08-23",
  "outbound_after": "19:00:00",
  "return_before": "22:00:00",
  "travelers": 2,
  "budget": 20000,
  "excluded_transport": ["bus"],
  "preferred_transport": ["train"],
  "max_transfers": 0,
  "hard_constraints": []
}
```

Поддерживаемые transport modes:

```text
train
flight
bus
suburban_train
```

Поддерживаемые constraint fields:

```text
budget
outbound_after
return_before
transport
max_transfers
```

---

## Hard и soft constraints

Пример soft-запроса:

```text
Желательно уложиться в 20 тысяч и вернуться до 22:00.
```

Такой budget/time может быть ослаблен, если exact-варианта нет.

Пример hard-запроса:

```text
Строго не дороже 20 тысяч.
На автобусе вообще не поеду.
Обязательно вернуться до 22:00.
```

Результат:

```json
{
  "budget": 20000,
  "return_before": "22:00:00",
  "excluded_transport": ["bus"],
  "hard_constraints": [
    "budget",
    "transport",
    "return_before"
  ]
}
```

Hard constraints никогда не должны появляться в `changes` negotiation alternative.

---

## Negotiation

Если exact Journey отсутствует, сервис ищет ближайшие допустимые варианты.

Например:

```text
SOFT:
budget <= 20 000 ₽

FOUND:
27 314 ₽
```

Сервис может вернуть:

```json
{
  "status": "negotiation_required",
  "alternatives": [
    {
      "kind": "single",
      "changes": [
        {
          "field": "budget",
          "old_value": 20000,
          "new_value": 27314
        }
      ]
    }
  ]
}
```

По умолчанию приоритет — минимальная single-constraint relaxation.

---

# API

Base URL локально:

```text
http://127.0.0.1:8010
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
  "service": "constraint-negotiator",
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
```

Force refresh:

```http
GET /api/v1/system/mcp?refresh=true
```

Tutu MCP в текущей интеграции предоставляет 16 tools.

## Metrics

```http
GET /api/v1/system/metrics
```

---

# Negotiator API

## Parse natural language

```http
POST /api/v1/negotiator/parse
```

Пример:

```json
{
  "text": "Хочу вдвоём из Москвы в Казань с 21 по 23 августа. Выехать после 19:00, желательно до 20 тысяч.",
  "reference_date": "2026-08-19"
}
```

Endpoint требует `OPENAI_API_KEY`.

Если ключ отсутствует, сервис продолжает работать, а AI parsing endpoint отвечает `503`.

## Negotiate from text

Raw/internal response:

```http
POST /api/v1/negotiator/from-text
```

Frontend-friendly response:

```http
POST /api/v1/negotiator/from-text/public
```

## Negotiate from TripSpec

Raw/internal response:

```http
POST /api/v1/negotiator/from-spec
```

Frontend-friendly response:

```http
POST /api/v1/negotiator/from-spec/public
```

Пример:

```json
{
  "trip": {
    "origin": "Москва",
    "destination": "Казань",
    "outbound_date": "2026-08-21",
    "return_date": "2026-08-23",
    "outbound_after": "19:00:00",
    "return_before": "22:00:00",
    "travelers": 2,
    "budget": 20000,
    "excluded_transport": ["bus"],
    "preferred_transport": ["train"],
    "max_transfers": 0,
    "hard_constraints": []
  }
}
```

Этот flow не требует OpenAI.

## Product search

```http
POST /api/v1/negotiator/products/search
```

Используется для прямого поиска travel products через Tutu provider.

---

# Checkout

Constraint Negotiator поддерживает handoff на реальное оформление Tutu.

```http
POST /api/v1/negotiator/checkout
```

Input:

```json
{
  "checkout_ref": {
    "transport": "railway",
    "...": "opaque Tutu fields"
  }
}
```

`checkout_ref` нельзя реконструировать вручную. Он передаётся в Tutu `create_checkout_link` как opaque metadata выбранного offer.

Response:

```json
{
  "status": "ready",
  "provider": "tutu",
  "kind": "deeplink",
  "primary_url": "https://...",
  "checkout_url": "https://...",
  "search_results_url": null,
  "fallback_note": null
}
```

Frontend должен показывать действие как `Перейти к оформлению` или `Купить на Туту`.

Checkout endpoint создаёт URL handoff. Он не означает, что покупка уже совершена.

## Checkout boundary

Внутренние модели сохраняют `checkout_ref`, а public API может не отдавать его frontend.

Предпочтительный flow:

```text
Frontend
   │ selected option id
   ▼
Backend / Agent
   │ stored JourneyOption + checkout_ref
   ▼
Constraint Negotiator /checkout
   │
   ▼
Tutu create_checkout_link
   │
   ▼
checkout URL
```

---

# Tutu MCP

Основные search tools:

```text
search_hotels
search_avia
search_rail
search_bus
search_etrain
search_multitransport
```

Также используются details/instructions tools и:

```text
create_checkout_link
fetch_resource
```

MCP client включает:

- explicit HTTP timeouts;
- overall deadline;
- retry transient network failures;
- exponential backoff;
- structured logging;
- latency/error/retry metrics;
- отсутствие retry для application-level MCP errors.

---

# Lazy OpenAI initialization

`OPENAI_API_KEY` нужен только для natural-language parsing.

Сервис не должен падать при startup без ключа.

Ожидаемое поведение:

```text
without OPENAI_API_KEY:

GET  /health                         -> 200
GET  /ready                          -> 200
GET  /api/v1/system/mcp              -> works
POST /api/v1/negotiator/from-spec    -> works
POST /api/v1/negotiator/checkout     -> works

POST /api/v1/negotiator/parse        -> 503
POST /api/v1/negotiator/from-text    -> 503
```

---

# Установка

Требования:

```text
Python 3.12
Docker
```

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
```

---

# Environment

Создать `.env` и заполнить необходимые runtime settings.

```env
OPENAI_API_KEY=
```

Секреты не должны попадать в git.

---

# Local run

```bash
python -m uvicorn app.main:app   --host 0.0.0.0   --port 8010
```

---

# Docker

Build:

```bash
docker build   -t constraint-negotiator   .
```

Run:

```bash
docker run   -d   --name constraint-negotiator   -p 8010:8010   --env-file .env   constraint-negotiator
```

Logs:

```bash
docker logs   --tail=100   constraint-negotiator
```

Stop:

```bash
docker rm -f constraint-negotiator
```

---

# Tests

```bash
python -m pytest -q
```

Текущее regression состояние:

```text
39 passed
```

Checkout regression:

```bash
python -m pytest tests/test_checkout.py -q
```

Lazy initialization regression:

```bash
python -m pytest tests/test_startup_without_openai.py -q
```

---

# Real checkout smoke

```bash
python -m scripts.smoke_checkout
```

Flow:

```text
health
  ↓
real Tutu search
  ↓
fresh checkout_ref
  ↓
POST /api/v1/negotiator/checkout
  ↓
real create_checkout_link
  ↓
Tutu deeplink
```

Ожидаемый финал:

```text
CHECKOUT E2E: OK
```

---

# Integration

Constraint Negotiator — самостоятельный decision service.

Если внешний AI Agent уже сформировал канонический `TripSpec`:

```http
POST /api/v1/negotiator/from-spec/public
```

Если сервис должен сам разобрать естественный язык:

```http
POST /api/v1/negotiator/from-text/public
```

Для exact checkout выбранного offer:

```http
POST /api/v1/negotiator/checkout
```

Канонические интеграционные объекты:

```text
TripSpec
JourneyOption
```

Внутренние Tutu metadata (`checkout_ref`) должны сохраняться до момента выбора offer.

---

# Связь с Trip Rescue

Constraint Negotiator отвечает за первоначальный подбор:

```text
user request
   ↓
TripSpec
   ↓
search
   ↓
JourneyOption
```

Trip Rescue работает после выбора Journey:

```text
accepted TripSpec + JourneyOption
   ↓
user changes plans
   ↓
minimal replanning
```

Оба сервиса используют совместимые доменные сущности и Tutu MCP, но решают разные задачи.

---

# Service

```text
name: constraint-negotiator
version: 0.2.0
default port: 8010
tests: 39 passed
```
