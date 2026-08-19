# Trip Rescue API Contract

Service:

```text
trip-rescue
```

Version:

```text
0.2.0
```

Default port:

```text
8020
```

---

# Main integration endpoint

```http
POST /api/v1/rescue/from-text/public
```

Используется, когда:

- пользователь уже имеет принятую поездку;
- изменяет планы текстом;
- необходимо сохранить максимум существующей поездки.

---

## Request

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
      "id": "outbound-id",
      "mode": "bus",
      "origin": "Москва",
      "destination": "Казань",
      "departure": "2026-08-21T22:45:00+03:00",
      "arrival": "2026-08-22T08:45:00+03:00",
      "price": 5000,
      "duration_minutes": 600,
      "transfers": 0,
      "carrier": "Евротранс"
    },

    "inbound": {
      "id": "inbound-id",
      "mode": "flight",
      "origin": "Казань",
      "destination": "Москва",
      "departure": "2026-08-23T07:05:00+03:00",
      "arrival": "2026-08-23T08:40:00+03:00",
      "price": 14428,
      "duration_minutes": 95,
      "transfers": 0,
      "carrier": "Аэрофлот"
    },

    "hotel": {
      "id": "hotel-id",
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

---

# Transport modes

Допустимые значения:

```text
train
flight
bus
suburban_train
```

---

# Constraint fields

```text
budget
outbound_after
return_before
transport
max_transfers
```

---

# Response

Основные поля public response:

```json
{
  "status": "candidates_found",

  "updated_trip": {},

  "changed_fields": [],

  "preserved_components": [],

  "replace_components": [],

  "reasons": [],

  "personalization": null,

  "candidates": []
}
```

---

# statuses

## no_change

Текущий Journey остаётся допустимым.

Frontend / orchestrator не должен инициировать новую бронь.

---

## candidates_found

Есть один или несколько exact candidates.

Рекомендуется показать:

```text
candidate[0]
```

как основной вариант.

---

## negotiation_required

Точного решения нет.

Candidate содержит:

```text
exact = false
relaxations != []
suggested_trip != null
```

Оркестратор должен показать пользователю компромисс и получить подтверждение.

Нельзя автоматически применять `suggested_trip` без пользовательского согласия.

---

## no_candidates

Нет допустимых вариантов.

Оркестратор может:

- попросить пользователя изменить hard constraints;
- изменить даты;
- изменить направление;
- перейти к новому полному поиску.

---

# Rescue Candidate

Public candidate содержит концептуально:

```json
{
  "id": "candidate-id",

  "replaced_components": [
    "inbound"
  ],

  "preserved_components": [
    "outbound",
    "hotel"
  ],

  "score": 1.010417,

  "exact": true,

  "relaxations": [],

  "suggested_trip": null,

  "summary": {
    "headline": "Меняем только дорогу обратно",
    "explanation": "Сохраняем дорогу туда и отель.",
    "price_delta_label": "−7 698 ₽",
    "previous_total_price": 22703,
    "new_total_price": 15005
  },

  "insights": [],

  "personalization": null,

  "journey": {}
}
```

---

# Negotiation relaxation

Пример:

```json
{
  "field": "budget",
  "title": "Увеличить бюджет",
  "description": "Для этого варианта нужно увеличить бюджет с 10 000 ₽ до 14 475 ₽.",
  "old_value": 10000,
  "new_value": 14475,
  "magnitude": 4475,
  "score": 0.0
}
```

Hard fields не должны появляться в `relaxations`.

---

# Journey Insight

Пример:

```json
{
  "type": "hotel_unused_nights",
  "severity": "warning",
  "title": "Часть брони отеля может не понадобиться",
  "description": "1 ночь может остаться неиспользованной.",
  "component": "hotel",
  "action": "search_shorter_hotel",
  "estimated_amount": 3275,
  "estimated_unused_nights": 1
}
```

---

# Personalization

Если:

```json
{
  "preference_profile_id": "user-123"
}
```

не передан:

```json
{
  "personalization": null
}
```

Если профиль существует:

```json
{
  "personalization": {
    "profile_id": "user-123",
    "interactions": 6,
    "applied": true
  }
}
```

Candidate также может содержать:

```json
{
  "personalization": {
    "preference_score": 2.252,
    "personalized_score": 0.319067,
    "rank_before": 3,
    "rank_after": 1,
    "reasons": [
      "Соответствует твоей привычке выбирать более выгодные варианты."
    ]
  }
}
```

---

# Preference feedback

```http
POST /api/v1/preferences/feedback
```

Request:

```json
{
  "profile_id": "user-123",
  "action": "choose",
  "candidate": {},
  "shown_candidates": []
}
```

Actions:

```text
like
dislike
choose
reject
```

Для `choose` рекомендуется передать все реально показанные варианты в `shown_candidates`.

---

# Preference profile

```http
GET /api/v1/preferences/{profile_id}
```

---

# Preference reset

```http
DELETE /api/v1/preferences/{profile_id}
```

---

# Preference reranking

```http
POST /api/v1/preferences/rerank
```

Используется для standalone personalization.

Для обычной интеграции предпочтительнее передавать:

```text
preference_profile_id
```

сразу в Rescue endpoint.

---

# Parser

```http
POST /api/v1/rescue/parse-update
```

Используется только если orchestration layer хочет отдельно выполнить parsing изменения.

Обычному клиенту предпочтительнее:

```text
/api/v1/rescue/from-text/public
```

---

# Deterministic Rescue

```http
POST /api/v1/rescue/from-spec/public
```

Используется, если внешний AI-agent уже самостоятельно получил новый `TripSpec`.

---

# Infrastructure

```http
GET /health
GET /ready
GET /api/v1/system/mcp
GET /api/v1/system/metrics
```

---

# Error handling

Client должен отдельно обрабатывать:

```text
4xx
5xx
network timeout
MCP/provider error
```

Не следует интерпретировать HTTP error как:

```text
no_candidates
```

`no_candidates` — валидный бизнес-результат с HTTP 200.

---

# Timeout

Rescue использует внешний Tutu MCP и может выполнять несколько поисков.

Клиенту рекомендуется устанавливать timeout не меньше:

```text
120–180 seconds
```

для hackathon/demo окружения.

---

# Ordering

Порядок `candidates` уже является итоговым ranking.

Клиент не должен самостоятельно сортировать candidates по цене, иначе:

- потеряется minimal-change ranking;
- потеряется personalization;
- могут потеряться policy priorities.

Используйте порядок API как authoritative ranking.