from __future__ import annotations

import json
import re

from datetime import date
from functools import lru_cache
from typing import Literal

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

    The LLM determines which TripSpec fields the user wants
    to change.

    `changed_fields` is authoritative for the patch itself.

    Hard/soft semantics are additionally verified
    deterministically after the LLM response.
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

    excluded_transport: list[
        TransportMode
    ]

    preferred_transport: list[
        TransportMode
    ]

    max_transfers: int | None

    hard_constraints: list[
        ConstraintField
    ]


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


Правила времени.

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


Hard constraints.

Если пользователь явно говорит:

- строго
- обязательно
- точно
- никак нельзя
- физически не могу
- ни в коем случае
- критично
- необходимо

то соответствующее ограничение должно быть добавлено
в hard_constraints.

Также строгими обычно являются формулировки:

- "не позже" для return_before;
- "не раньше" / "только после" для outbound_after;
- "не больше" / "не дороже" / "максимум" для budget;
- явный запрет конкретного вида транспорта;
- строгий максимум числа пересадок.

Но если в той же части сообщения пользователь говорит:

- желательно
- хотелось бы
- лучше
- предпочитаю
- по возможности
- если получится
- не обязательно
- не строго

то соответствующее условие является МЯГКИМ
и НЕ должно добавляться в hard_constraints.


Примеры.

"теперь обязательно надо вернуться до 8"

-> return_before изменяется
-> return_before добавляется в hard_constraints


"автобус теперь вообще исключён"

-> excluded_transport содержит bus
-> transport добавляется в hard_constraints


"максимум 20 тысяч, строго"

-> budget = 20000
-> budget добавляется в hard_constraints


"обязательно быть в Москве до 8,
но желательно уложиться в 10 тысяч"

-> return_before = "08:00:00"
-> budget = 10000

-> return_before является hard
-> budget НЕ является hard


Если формулировка мягкая:

- желательно
- хотелось бы
- лучше
- предпочитаю
- по возможности

то НЕ добавляй соответствующее поле
в hard_constraints.


Важно.

changed_fields содержит ТОЛЬКО реально изменённые поля.

Для полей, которые не меняются:

- scalar nullable fields -> null
- list fields -> []

Значения полей вне changed_fields
игнорируются приложением.


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


Не меняй даты или город самостоятельно
из-за изменения времени.

Относительные даты интерпретируй
относительно REFERENCE_DATE.
"""


NON_NULLABLE_FIELDS: set[
    TripField
] = {
    TripField.ORIGIN,
    TripField.DESTINATION,
    TripField.OUTBOUND_DATE,
    TripField.RETURN_DATE,
    TripField.TRAVELERS,
}


TRIP_FIELD_TO_CONSTRAINT: dict[
    TripField,
    ConstraintField,
] = {
    TripField.BUDGET: (
        ConstraintField.BUDGET
    ),

    TripField.OUTBOUND_AFTER: (
        ConstraintField.OUTBOUND_AFTER
    ),

    TripField.RETURN_BEFORE: (
        ConstraintField.RETURN_BEFORE
    ),

    TripField.EXCLUDED_TRANSPORT: (
        ConstraintField.TRANSPORT
    ),

    TripField.MAX_TRANSFERS: (
        ConstraintField.MAX_TRANSFERS
    ),
}


SOFT_MARKERS: tuple[
    str,
    ...
] = (
    "желательно",
    "хотелось бы",
    "лучше",
    "предпочитаю",
    "по возможности",
    "если получится",
    "если возможно",
    "если можно",
    "не обязательно",
    "необязательно",
    "не строго",
    "не критично",
    "можно позже",
    "можно раньше",
)


HARD_MARKERS: tuple[
    str,
    ...
] = (
    "обязательно",
    "строго",
    "точно",
    "никак нельзя",
    "физически не могу",
    "ни в коем случае",
    "критично",
    "необходимо",
)


FIELD_CUE_PATTERNS: dict[
    TripField,
    tuple[
        re.Pattern[str],
        ...
    ],
] = {
    TripField.RETURN_BEFORE: (
        re.compile(
            r"\bвернут\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bвозвращ\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bприбы\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bприех\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bуспеть\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bбыть\b.{0,60}\bдо\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bне\s+позже\b",
            re.IGNORECASE,
        ),
    ),

    TripField.OUTBOUND_AFTER: (
        re.compile(
            r"\bвыех\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bвыезд\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bотправ\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bне\s+раньше\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bтолько\s+после\b",
            re.IGNORECASE,
        ),
    ),

    TripField.BUDGET: (
        re.compile(
            r"\bбюджет\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bруб\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"₽",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bтысяч\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bтыс\.?",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bуложит\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bдороже\b",
            re.IGNORECASE,
        ),
    ),

    TripField.EXCLUDED_TRANSPORT: (
        re.compile(
            r"\bавтобус\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bпоезд\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bсамол[её]т\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bавиа\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bэлектрич\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bтранспорт\w*",
            re.IGNORECASE,
        ),
    ),

    TripField.MAX_TRANSFERS: (
        re.compile(
            r"\bпересад\w*",
            re.IGNORECASE,
        ),
    ),
}


FIELD_IMPLICIT_HARD_PATTERNS: dict[
    TripField,
    tuple[
        re.Pattern[str],
        ...
    ],
] = {
    TripField.RETURN_BEFORE: (
        re.compile(
            r"\bне\s+позже\b",
            re.IGNORECASE,
        ),
    ),

    TripField.OUTBOUND_AFTER: (
        re.compile(
            r"\bне\s+раньше\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bтолько\s+после\b",
            re.IGNORECASE,
        ),
    ),

    TripField.BUDGET: (
        re.compile(
            r"\bмаксимум\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bне\s+больше\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bне\s+дороже\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bпотолок\b",
            re.IGNORECASE,
        ),
    ),

    TripField.EXCLUDED_TRANSPORT: (
        re.compile(
            r"\bисключ[её]н\w*",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bисключить\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bнельзя\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bбез\s+"
            r"(?:автобус\w*|поезд\w*|"
            r"самол[её]т\w*|авиа\w*|"
            r"электрич\w*)",
            re.IGNORECASE,
        ),
    ),

    TripField.MAX_TRANSFERS: (
        re.compile(
            r"\bмаксимум\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bне\s+больше\b",
            re.IGNORECASE,
        ),
    ),
}


CLAUSE_SPLIT_PATTERN = re.compile(
    r"""
    (?:
        [.!?;\n]+
        |
        ,\s*
        (?:
            а
            |
            но
            |
            и
            |
            зато
            |
            при\s+этом
        )
        \s+
    )
    """,
    re.IGNORECASE
    | re.VERBOSE,
)


ConstraintStance = Literal[
    "hard",
    "soft",
]


class TripUpdateParser:
    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        settings = get_settings()

        if (
            settings.openai_api_key
            is None
        ):
            raise RuntimeError(
                "OPENAI_API_KEY is required "
                "for TripUpdateParser"
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
            self.llm
            .with_structured_output(
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
        clean_message = (
            message.strip()
        )

        if not clean_message:
            raise ValueError(
                "Trip update message is empty"
            )

        current_trip_json = (
            json.dumps(
                previous_trip.model_dump(
                    mode="json"
                ),
                ensure_ascii=False,
            )
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
            self.structured_llm
            .ainvoke(
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

        updated_trip = (
            apply_trip_update(
                previous_trip=(
                    previous_trip
                ),
                update=result,
            )
        )

        return (
            apply_semantic_hardening(
                previous_trip=(
                    previous_trip
                ),
                updated_trip=(
                    updated_trip
                ),
                update=result,
                message=(
                    clean_message
                ),
            )
        )


def apply_trip_update(
    *,
    previous_trip: TripSpec,
    update: ParsedTripUpdate,
) -> TripSpec:
    """
    Deterministically apply the LLM-produced patch.

    The LLM decides WHAT the user changed.
    Python decides HOW the patch modifies TripSpec.

    Hard/soft semantics are normalized separately
    by apply_semantic_hardening().
    """

    payload = (
        previous_trip.model_dump(
            mode="json"
        )
    )

    seen: set[
        TripField
    ] = set()

    for field in (
        update.changed_fields
    ):
        if field in seen:
            continue

        seen.add(
            field
        )

        value = getattr(
            update,
            field.value,
        )

        if (
            field
            in NON_NULLABLE_FIELDS
            and value is None
        ):
            raise ValueError(
                f"{field.value} "
                "cannot be cleared"
            )

        payload[
            field.value
        ] = value

    return (
        TripSpec.model_validate(
            payload
        )
    )


def apply_semantic_hardening(
    *,
    previous_trip: TripSpec,
    updated_trip: TripSpec,
    update: ParsedTripUpdate,
    message: str,
) -> TripSpec:
    """
    Deterministic safety layer for hard constraints.

    Important design:

    - LLM still understands natural language.
    - LLM output is NOT trusted as the sole source
      of hard/soft semantics.
    - Existing hard constraints are preserved unless
      the user explicitly softens/removes them.
    - Strong wording deterministically hardens
      the corresponding changed constraint.
    - Soft wording deterministically prevents that
      constraint from becoming hard.
    - Inactive constraints cannot remain hard.
    """

    hard_constraints = set(
        previous_trip.hard_constraints
    )

    # Keep LLM additions too, but never rely on them alone.
    hard_constraints.update(
        updated_trip.hard_constraints
    )

    changed_fields = {
        field
        for field
        in update.changed_fields
    }

    negotiable_changed = {
        field
        for field
        in changed_fields
        if field
        in TRIP_FIELD_TO_CONSTRAINT
    }

    for field in (
        negotiable_changed
    ):
        constraint = (
            TRIP_FIELD_TO_CONSTRAINT[
                field
            ]
        )

        stance = (
            infer_constraint_stance(
                message=message,
                field=field,
                changed_negotiable_fields=(
                    negotiable_changed
                ),
            )
        )

        if stance == "hard":
            hard_constraints.add(
                constraint
            )

        elif stance == "soft":
            hard_constraints.discard(
                constraint
            )

    # A constraint with no underlying active value
    # cannot stay hard.
    for constraint in list(
        hard_constraints
    ):
        if not _constraint_is_active(
            trip=updated_trip,
            constraint=constraint,
        ):
            hard_constraints.discard(
                constraint
            )

    payload = (
        updated_trip.model_dump(
            mode="json"
        )
    )

    payload[
        "hard_constraints"
    ] = sorted(
        (
            constraint.value
            for constraint
            in hard_constraints
        )
    )

    return (
        TripSpec.model_validate(
            payload
        )
    )


def infer_constraint_stance(
    *,
    message: str,
    field: TripField,
    changed_negotiable_fields: set[
        TripField
    ]
    | None = None,
) -> ConstraintStance | None:
    """
    Infer hard/soft stance for one changed field.

    We first look only at clauses that mention this field.

    This is important for messages like:

        "обязательно быть до 8,
         но желательно уложиться в 10 тысяч"

    where:
        return_before -> hard
        budget        -> soft
    """

    normalized = (
        _normalize_text(
            message
        )
    )

    clauses = (
        _split_clauses(
            normalized
        )
    )

    stance: (
        ConstraintStance
        | None
    ) = None

    matched_clause = False

    for clause in clauses:
        if not _clause_mentions_field(
            clause=clause,
            field=field,
        ):
            continue

        matched_clause = True

        clause_stance = (
            _infer_clause_stance(
                clause=clause,
                field=field,
            )
        )

        # Last explicit mention wins.
        if clause_stance is not None:
            stance = (
                clause_stance
            )

    if matched_clause:
        return stance

    # Safe fallback:
    #
    # If the user changes exactly one negotiable field,
    # global wording can safely refer to that field.
    changed = (
        changed_negotiable_fields
        or set()
    )

    if len(changed) == 1:
        return (
            _infer_clause_stance(
                clause=normalized,
                field=field,
            )
        )

    return None


def _infer_clause_stance(
    *,
    clause: str,
    field: TripField,
) -> ConstraintStance | None:
    # Soft markers are evaluated FIRST.
    #
    # This prevents:
    #
    # "не обязательно"
    #
    # from being classified as hard because it also
    # contains the substring "обязательно".
    if _contains_any(
        clause,
        SOFT_MARKERS,
    ):
        return "soft"

    if _contains_any(
        clause,
        HARD_MARKERS,
    ):
        return "hard"

    patterns = (
        FIELD_IMPLICIT_HARD_PATTERNS
        .get(
            field,
            (),
        )
    )

    if any(
        pattern.search(
            clause
        )
        is not None
        for pattern
        in patterns
    ):
        return "hard"

    return None


def _clause_mentions_field(
    *,
    clause: str,
    field: TripField,
) -> bool:
    patterns = (
        FIELD_CUE_PATTERNS.get(
            field,
            (),
        )
    )

    return any(
        pattern.search(
            clause
        )
        is not None
        for pattern
        in patterns
    )


def _split_clauses(
    value: str,
) -> list[str]:
    parts = (
        CLAUSE_SPLIT_PATTERN
        .split(
            value
        )
    )

    return [
        part.strip()
        for part
        in parts
        if part.strip()
    ]


def _normalize_text(
    value: str,
) -> str:
    normalized = (
        value
        .lower()
        .replace(
            "ё",
            "е",
        )
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return (
        normalized.strip()
    )


def _contains_any(
    value: str,
    markers: tuple[
        str,
        ...
    ],
) -> bool:
    return any(
        marker in value
        for marker
        in markers
    )


def _constraint_is_active(
    *,
    trip: TripSpec,
    constraint: ConstraintField,
) -> bool:
    if (
        constraint
        == ConstraintField.BUDGET
    ):
        return (
            trip.budget
            is not None
        )

    if (
        constraint
        == ConstraintField.OUTBOUND_AFTER
    ):
        return (
            trip.outbound_after
            is not None
        )

    if (
        constraint
        == ConstraintField.RETURN_BEFORE
    ):
        return (
            trip.return_before
            is not None
        )

    if (
        constraint
        == ConstraintField.TRANSPORT
    ):
        return bool(
            trip.excluded_transport
            or trip.preferred_transport
        )

    if (
        constraint
        == ConstraintField.MAX_TRANSFERS
    ):
        return (
            trip.max_transfers
            is not None
        )

    return False


@lru_cache(maxsize=1)
def get_trip_update_parser() -> (
    TripUpdateParser
):
    return TripUpdateParser()