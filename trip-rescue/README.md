# Trip Rescue

Trip Rescue — decision layer для уже выбранной поездки.

Сервис не строит путешествие заново при каждом изменении планов. Он принимает текущий TripSpec, уже выбранный Journey и новое сообщение пользователя, определяет, какая часть поездки перестала подходить, сохраняет всё ещё валидное и через Tutu MCP ищет минимальную замену.

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
- искать обратный транспорт в предыдущий календарный день, если это требуется дедлайном прибытия;
- проверять полную feasibility после merge;
- ранжировать варианты по минимальности изменений;
- находить ближайшие компромиссы, если точного варианта нет;
- никогда не ослаблять hard constraints в negotiation fallback;
- определять потенциально ненужные ночи отеля после изменения маршрута;
- обучаться на действиях like / dislike / choose / reject;
- персонализировать ranking;
- объяснять влияние пользовательских предпочтений;
- хранить preference profile между перезапусками сервиса;
- работать в Docker.

---

## Архитектура

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
            ├── exact candidates
            │
            └── negotiation fallback
                    │
                    ▼
                soft relaxations
            │
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
         Public API
```

---

## Ключевой принцип

LLM не принимает критические решения о валидности поездки.

LLM используется для:

- parsing естественного языка;
- понимания того, какие поля изменил пользователь.

Детерминированный Python-код отвечает за:

- применение TripSpec patch;
- hard/soft semantics;
- feasibility;
- component preservation;
- relaxation policy;
- ranking;
- validation.

---

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
"23 августа мне обязательно нужно быть в Москве до 8 утра"
```

превращается в:

```json
{
  "return_before": "08:00:00",
  "hard_constraints": [
    "return_before"
  ]
}
```

После semantic hardening этот hard constraint не может быть ослаблен Negotiation Fallback.

Например система не имеет права предложить:

```text
08:00 → 08:40
```

если `return_before` является hard.

---

## Soft constraints

Например:

```text
"желательно уложиться в 10 тысяч"
```

может быть преобразовано в:

```json
{
  "budget": 10000
}
```

без:

```text
budget
```

в `hard_constraints`.

Если точного варианта до 10 000 ₽ нет, система может предложить минимальное увеличение бюджета.

---

## Minimal Replanning

Допустим пользователь уже выбрал:

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
"Теперь обязательно нужно быть в Москве до 8 утра"
```

Trip Rescue определяет:

```text
outbound  → valid → preserve
hotel     → valid → preserve
inbound   → invalid → replace
```

И выполняет поиск только обратной дороги.

---

## Journey Intelligence

После replanning сервис анализирует побочные эффекты.

Например новый обратный транспорт отправляется вечером предыдущего дня, хотя отель забронирован до следующего дня.

Ответ может содержать:

```json
{
  "type": "hotel_unused_nights",
  "severity": "warning",
  "action": "search_shorter_hotel",
  "estimated_amount": 3275,
  "estimated_unused_nights": 1
}
```

Это означает, что пользователь потенциально может уменьшить бронь и сэкономить деньги.

---

## Negotiation Fallback

Если exact candidate отсутствует, сервис не возвращает просто `no_candidates`.

Для soft constraints он ищет ближайшие допустимые компромиссы.

Например:

```text
HARD:
вернуться до 08:00

SOFT:
бюджет ≤ 10 000 ₽
```

Если подходящий маршрут стоит 14 475 ₽:

```json
{
  "status": "negotiation_required",
  "relaxations": [
    {
      "field": "budget",
      "old_value": 10000,
      "new_value": 14475
    }
  ]
}
```

При этом:

```text
return_before = 08:00
```

остаётся неизменным.

---

## Preference Learning

Сервис поддерживает пользовательский preference profile.

Сигналы:

```text
like
dislike
choose
reject
```

Из действий пользователя могут обучаться:

```text
transport affinity
price sensitivity
duration sensitivity
transfer sensitivity
hotel quality sensitivity
```

Пример:

пользователь несколько раз выбирает более дешёвый автобус.

До personalization:

```text
Candidate A → rank 1
Candidate B → rank 2
Candidate C → rank 3
```

После обучения:

```text
Candidate C → rank 1
```

При этом feasibility не меняется.

Preference Learning влияет только на ranking уже допустимых вариантов.

---

## Preference persistence

Локально:

```text
./data/preferences.json
```

В Docker:

```text
/data/preferences.json
```

Docker Compose использует persistent volume:

```text
trip-rescue-data
```

Поэтому preference profiles сохраняются после restart контейнера.

---

# API

Base URL локально:

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

---

## Health

```http
GET /health
```

Ответ:

```json
{
  "status": "ok",
  "service": "trip-rescue",
  "version": "0.2.0"
}
```

---

## Readiness

```http
GET /ready
```

---

## MCP diagnostics

```http
GET /api/v1/system/mcp
```

Для принудительного refresh:

```http
GET /api/v1/system/mcp?refresh=true
```

---

## Metrics

```http
GET /api/v1/system/metrics
```

---

# Rescue API

Основной production endpoint:

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
    "outbound": {
      "id": "outbound",
      "mode": "bus",
      "origin": "Москва",
      "destination": "Казань",
      "departure": "2026-08-21T22:45:00+03:00",
      "arrival": "2026-08-22T08:45:00+03:00",
      "price": 5000,
      "duration_minutes": 600,
      "transfers": 0
    },
    "inbound": {
      "id": "inbound",
      "mode": "flight",
      "origin": "Казань",
      "destination": "Москва",
      "departure": "2026-08-23T07:05:00+03:00",
      "arrival": "2026-08-23T08:40:00+03:00",
      "price": 14428,
      "duration_minutes": 95,
      "transfers": 0
    },
    "hotel": {
      "id": "hotel",
      "name": "Гостевой Дом Мансарда",
      "price": 3275,
      "stars": 0,
      "rating": 7.03,
      "review_count": 48,
      "check_in": "2026-08-22",
      "check_out": "2026-08-23",
      "nights": 1
    }
  },
  "message": "Теперь обязательно нужно быть в Москве до 8 утра",
  "reference_date": "2026-08-19",
  "preference_profile_id": "user-123"
}
```

`preference_profile_id` является optional.

---

## Rescue statuses

Сервис может вернуть:

```text
no_change
candidates_found
negotiation_required
no_candidates
```

### no_change

Текущая поездка всё ещё удовлетворяет изменению.

### candidates_found

Найдены exact candidates.

### negotiation_required

Exact candidate отсутствует, но существует допустимый вариант после минимального ослабления soft constraints.

### no_candidates

Не удалось найти допустимый вариант даже после разрешённых soft relaxations.

---

# Other Rescue endpoints

Raw text response:

```http
POST /api/v1/rescue/from-text
```

Deterministic TripSpec input:

```http
POST /api/v1/rescue/from-spec
```

Public deterministic TripSpec endpoint:

```http
POST /api/v1/rescue/from-spec/public
```

Parser endpoint:

```http
POST /api/v1/rescue/parse-update
```

---

# Preference API

## Feedback

```http
POST /api/v1/preferences/feedback
```

Actions:

```text
like
dislike
choose
reject
```

При `choose` желательно передавать все варианты, которые видел пользователь.

Это позволяет обучать pairwise preferences.

---

## Profile

```http
GET /api/v1/preferences/{profile_id}
```

---

## Reset profile

```http
DELETE /api/v1/preferences/{profile_id}
```

---

## Standalone reranking

```http
POST /api/v1/preferences/rerank
```

---

# Tutu MCP

Trip Rescue использует Tutu MCP как источник реальных travel offers.

Production diagnostics должен возвращать:

```text
provider = tutu_mcp
status = connected
```

В текущей интеграции используется 16 MCP tools.

---

# Установка

Требования:

```text
Python 3.12
Docker
Docker Compose
```

Создание virtualenv:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Установка:

```bash
python -m pip install -r requirements.lock.txt
```

---

# Environment

Создать `.env` на основе:

```text
.env.example
```

Preference store локально:

```env
PREFERENCE_STORE_PATH=./data/preferences.json
```

Docker Compose переопределяет его на:

```text
/data/preferences.json
```

---

# Local run

```bash
python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8020
```

---

# Tests

```bash
python -m pytest -q
```

Текущее regression состояние:

```text
63 passed
```

Semantic hardening:

```bash
python -m pytest \
  tests/test_parser_hardening.py \
  -q
```

Текущее состояние:

```text
5 passed
```

---

# End-to-end smoke

Основной Rescue:

```bash
python -m scripts.smoke_rescue
```

Negotiation:

```bash
python -m scripts.smoke_fallback
```

Preference Learning:

```bash
python -m scripts.smoke_preferences
```

---

# Docker

Build:

```bash
docker compose up -d --build
```

Status:

```bash
docker compose ps
```

Logs:

```bash
docker compose logs \
  --tail=100 \
  trip-rescue
```

Health:

```bash
curl http://127.0.0.1:8020/health
```

MCP:

```bash
curl \
  'http://127.0.0.1:8020/api/v1/system/mcp?refresh=true'
```

Stop:

```bash
docker compose down
```

---

# Persistence check

```bash
docker exec \
  trip-rescue \
  cat /data/preferences.json
```

Restart:

```bash
docker compose restart
```

Затем:

```bash
curl \
  http://127.0.0.1:8020/api/v1/preferences/<profile_id>
```

Профиль должен сохраниться.

---

# Integration

Для интеграции с общим travel agent рекомендуется использовать:

```http
POST /api/v1/rescue/from-text/public
```

Если главный AI-agent уже самостоятельно построил новый TripSpec:

```http
POST /api/v1/rescue/from-spec/public
```

Preference feedback отправляется отдельно после пользовательского действия.

Подробнее:

```text
docs/API_CONTRACT.md
docs/INTEGRATION_GUIDE.md
```

---

# Service

```text
name: trip-rescue
version: 0.2.0
default port: 8020
```