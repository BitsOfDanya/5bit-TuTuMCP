from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.models.rescue import TripField
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)


class ParsedTripUpdate(BaseModel):
    """
    LLM boundary DTO.

    All fields are deliberately JSON-schema-friendly.
    `changed_fields` determines which values are actually
    applied to the existing TripSpec.

    Nullable value + changed_fields allows commands like:
        "Бюджет больше не важен"
        -> changed_fields=["budget"], budget=null
    """

    changed_fields: list[TripField]

    origin: str | None
    destination: str | None

    outbound_date: str | None
    return_date: str | None

    outbound_after: str | None
    return_before: str | None

    travelers: int | None
    budget: int | None

    excluded_transport: list[TransportMode]
    preferred_transport: list[TransportMode]

    max_transfers: int | None

    hard_constraints: list[ConstraintField]


SYSTEM_PROMPT = """
Ты — parser изменения уже выбранной поездки.

У тебя есть CURRENT_TRIP — текущие условия поездки.
Пользователь пишет новое сообщение с изменением планов.

Твоя задача ТОЛЬКО определить, какие поля TripSpec он хочет изменить.

Ты НЕ:
- ищешь билеты;
- ищешь отели;
- придумываешь цены;
- рекомендуешь маршруты;
- меняешь поля, про которые пользователь ничего не сказал.

Доступные changed_fields:

origin
destination
outbound_date
return_date
outbound_after
return_before
travelers
budget
excluded_transport
preferred_transport
max_transfers
hard_constraints

Правила времени:

outbound_after:
самое раннее допустимое время отправления ТУДА.

Пример:
"теперь смогу выехать только после 21"
-> outbound_after = "21:00:00"

return_before:
крайнее допустимое время ПРИБЫТИЯ ОБРАТНО.

Пример:
"теперь обязательно надо быть в Москве до 8 утра"
-> return_before = "08:00:00"

Транспорт:

самолёт / авиа -> flight
поезд -> train
автобус -> bus
электричка -> suburban_train

Если пользователь запрещает транспорт:
-> excluded_transport.

Если пользователь только предпочитает:
-> preferred_transport.

Hard constraints:

Если пользователь явно говорит:
- строго
- обязательно
- точно
- никак нельзя
- физически не могу
- ни в коем случае

то соответствующее ограничение должно быть добавлено
в hard_constraints.

Примеры:

"теперь обязательно надо вернуться до 8"
-> return_before изменяется
-> return_before добавляется в hard_constraints

"автобус теперь вообще исключён"
-> excluded_transport содержит bus
-> transport добавляется в hard_constraints

"максимум 20 тысяч, строго"
-> budget=20000
-> budget добавляется в hard_constraints

Если формулировка мягкая:
- желательно
- хотелось бы
- лучше
- предпочитаю

то НЕ добавляй поле в hard_constraints.

Важно:

changed_fields содержит ТОЛЬКО реально изменённые поля.

Для полей, которые не меняются:
- scalar nullable fields -> null
- list fields -> []

Значения полей вне changed_fields игнорируются приложением.

Если пользователь явно снимает nullable-ограничение:

"время возвращения больше не важно"
-> changed_fields=["return_before"]
-> return_before=null

"по бюджету ограничений больше нет"
-> changed_fields=["budget"]
-> budget=null

Для очистки списка:

"автобус теперь можно"
если раньше bus был excluded:
-> changed_fields=["excluded_transport"]
-> excluded_transport без bus.

Не меняй даты или город самостоятельно из-за изменения времени.

Относительные даты интерпретируй относительно REFERENCE_DATE.
"""


NON_NULLABLE_FIELDS: set[TripField] = {
    TripField.ORIGIN,
    TripField.DESTINATION,
    TripField.OUTBOUND_DATE,
    TripField.RETURN_DATE,
    TripField.TRAVELERS,
}


class TripUpdateParser:
    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        settings = get_settings()

        if settings.openai_api_key is None:
            raise RuntimeError(
                "OPENAI_API_KEY is required for TripUpdateParser"
            )

        api_key = (
            settings.openai_api_key
            .get_secret_value()
        )

        self.llm = ChatOpenAI(
            model=(
                model
                or settings.openai_model
            ),
            api_key=api_key,
            temperature=0,
        )

        self.structured_llm = (
            self.llm.with_structured_output(
                ParsedTripUpdate
            )
        )

    async def parse(
        self,
        *,
        previous_trip: TripSpec,
        message: str,
        reference_date: date,
    ) -> TripSpec:
        clean_message = message.strip()

        if not clean_message:
            raise ValueError(
                "Trip update message is empty"
            )

        current_trip_json = json.dumps(
            previous_trip.model_dump(
                mode="json"
            ),
            ensure_ascii=False,
        )

        prompt = f"""
REFERENCE_DATE:
{reference_date.isoformat()}

CURRENT_TRIP:
{current_trip_json}

USER_UPDATE:
{clean_message}
"""

        result = await (
            self.structured_llm.ainvoke(
                [
                    (
                        "system",
                        SYSTEM_PROMPT,
                    ),
                    (
                        "human",
                        prompt,
                    ),
                ]
            )
        )

        if not isinstance(
            result,
            ParsedTripUpdate,
        ):
            result = (
                ParsedTripUpdate
                .model_validate(
                    result
                )
            )

        return apply_trip_update(
            previous_trip=previous_trip,
            update=result,
        )


def apply_trip_update(
    *,
    previous_trip: TripSpec,
    update: ParsedTripUpdate,
) -> TripSpec:
    """
    Deterministically apply the LLM-produced patch.

    The LLM decides WHAT the user changed.
    Python decides HOW it changes TripSpec.
    """

    payload = (
        previous_trip.model_dump(
            mode="json"
        )
    )

    seen: set[TripField] = set()

    for field in update.changed_fields:
        if field in seen:
            continue

        seen.add(field)

        value = getattr(
            update,
            field.value,
        )

        if (
            field in NON_NULLABLE_FIELDS
            and value is None
        ):
            raise ValueError(
                f"{field.value} cannot be cleared"
            )

        payload[
            field.value
        ] = value

    return TripSpec.model_validate(
        payload
    )


@lru_cache(maxsize=1)
def get_trip_update_parser() -> TripUpdateParser:
    return TripUpdateParser()