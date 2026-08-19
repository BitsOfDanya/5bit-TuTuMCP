# Integration Guide

Этот документ предназначен для общего AI travel agent / backend.

---

# Когда вызывать Trip Rescue

Trip Rescue вызывается только если у пользователя уже существует:

```text
accepted TripSpec
+
accepted Journey
```

и после этого пользователь сообщает об изменении планов.

Примеры:

```text
"Теперь надо вернуться до 8 утра"

"Бюджет уменьшился до 15 тысяч"

"Автобус больше не подходит"

"Теперь могу выехать только после 21"

"Хочу максимум одну пересадку"
```

---

# Когда НЕ вызывать Trip Rescue

Если поездка ещё не была выбрана, должен работать обычный planning/search flow.

```text
New trip
→ обычный AI travel agent

Existing accepted trip changed
→ Trip Rescue
```

---

# Recommended orchestration

```text
User
 │
 ▼
Unified AI Agent
 │
 ├── no accepted journey
 │       │
 │       ▼
 │   Normal Travel Search
 │
 └── accepted journey exists
         │
         ▼
     detect trip change
         │
         ▼
 POST /api/v1/rescue/from-text/public
         │
         ▼
      Trip Rescue
```

---

# Что хранить в основном backend

Основной backend должен сохранять:

```text
current TripSpec
current accepted Journey
preference_profile_id
```

Trip Rescue не должен быть source of truth для пользовательской поездки.

Он является decision service.

---

# Главный endpoint

```http
POST /api/v1/rescue/from-text/public
```

Backend передаёт:

```text
current_trip
current_journey
message
reference_date
preference_profile_id
```

---

# Обработка ответа

## candidates_found

Показать пользователю ranked candidates.

Основной recommendation:

```text
candidates[0]
```

Но UI может позволить выбрать любой candidate.

После выбора:

```text
1. основной backend сохраняет новый Journey
2. current TripSpec заменяется на updated_trip
3. отправляется preference feedback action=choose
```

---

## negotiation_required

Не применять автоматически.

Показать:

```text
summary
relaxations
suggested_trip
journey
```

Например:

```text
Точный вариант до 10 000 ₽ не найден.

Можно сохранить обязательное возвращение до 08:00,
если увеличить бюджет до 14 475 ₽.
```

Если пользователь принимает:

```text
1. сохранить suggested_trip
2. сохранить выбранный Journey
3. отправить choose feedback
```

---

## no_change

Ничего не заменять.

Текущий Journey остаётся accepted.

---

## no_candidates

Попросить изменить фундаментальные условия.

Например:

```text
дату
город
hard deadline
transport ban
```

---

# Preference profile ID

В production не использовать пользовательский текстовый nickname.

Рекомендуемый вариант:

```text
internal_user_id
```

или:

```text
UUID
```

Например:

```text
9c8dd65b-82d6-48f1-90d9-b3f383abeb11
```

---

# Feedback

После UI actions отправлять:

```http
POST /api/v1/preferences/feedback
```

### Like

Пользователь положительно оценил candidate.

### Dislike

Пользователь отрицательно оценил candidate.

### Choose

Пользователь реально выбрал candidate.

Самый сильный сигнал.

Передавать:

```text
candidate
shown_candidates
```

### Reject

Пользователь явно отказался от candidate.

---

# Important

Personalization не является feasibility layer.

Flow:

```text
Tutu candidates
→ deterministic feasibility
→ rescue policy
→ exact/fallback separation
→ base ranking
→ preference ranking
```

Поэтому preference profile не может сделать недопустимый маршрут допустимым.

---

# Hard constraints

Если Trip Rescue возвращает:

```json
{
  "hard_constraints": [
    "return_before"
  ]
}
```

frontend/backend не должен самостоятельно ослаблять это ограничение.

---

# Candidate ordering

Порядок candidates уже рассчитан.

Не делать:

```javascript
candidates.sort((a, b) => {
  return a.journey.total_price - b.journey.total_price
})
```

Это уничтожит ranking сервиса.

---

# Booking URLs

Journey segments могут содержать:

```text
booking_url
```

Если URL присутствует, frontend может использовать его для перехода к Tutu booking flow.

Если:

```text
booking_url = null
```

frontend не должен генерировать URL самостоятельно.

---

# Suggested frontend states

```text
rescue_loading
rescue_exact
rescue_negotiation
rescue_no_change
rescue_no_candidates
rescue_error
```

---

# Recommended UI for exact result

```text
Планы изменились

Мы сохранили:
✓ дорогу туда
✓ отель

Нужно заменить:
✕ дорогу обратно

Лучший вариант:
Казань → Москва
19:55 → 05:55
6 200 ₽

Вся поездка:
14 475 ₽

Экономия:
8 228 ₽
```

---

# Recommended UI for negotiation

```text
Точного варианта нет

Обязательное условие:
✓ быть в Москве до 08:00

Чтобы сохранить его:
~ увеличить бюджет
10 000 ₽ → 14 475 ₽

[Принять]
[Посмотреть другие]
```

---

# Journey Intelligence UI

Если candidate содержит:

```text
insights
```

не игнорировать их.

Например:

```text
Часть брони отеля может не понадобиться

Можно потенциально сэкономить:
3 275 ₽
```

---

# Recommended backend timeout

Для Rescue:

```text
180 seconds
```

Для:

```text
/health
/ready
/preferences/*
```

достаточно значительно меньшего timeout.

---

# Retry policy

Можно retry:

```text
network error
provider timeout
temporary 5xx
```

Не retry автоматически:

```text
4xx validation error
no_candidates
negotiation_required
```

---

# Deployment contract

Backend должен получать base URL через environment:

```env
TRIP_RESCUE_URL=http://trip-rescue:8020
```

В локальной разработке:

```env
TRIP_RESCUE_URL=http://127.0.0.1:8020
```

Никогда не хардкодить production IP в приложении.

---

# Minimal integration

Для первой интеграции достаточно трёх действий:

```text
POST rescue/from-text/public

POST preferences/feedback

GET health
```

Остальные endpoints являются дополнительными.