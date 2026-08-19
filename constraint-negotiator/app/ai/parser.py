from __future__ import annotations

from datetime import date
from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)


class ParsedTripSpec(BaseModel):
    """
    OpenAI Structured Outputs DTO.

    Important:
    hard_constraints is intentionally a LIST here.

    Pydantic serializes set[...] into JSON Schema
    with uniqueItems=true, which is not supported by
    OpenAI Structured Outputs.

    After parsing we convert this DTO into our normal
    domain TripSpec, where hard_constraints can remain
    a set.
    """

    origin: str = Field(
        min_length=2
    )

    destination: str = Field(
        min_length=2
    )

    outbound_date: date
    return_date: date

    outbound_after: str | None = None
    return_before: str | None = None

    travelers: int = Field(
        default=1,
        ge=1,
        le=9,
    )

    budget: int | None = Field(
        default=None,
        gt=0,
    )

    excluded_transport: list[
        TransportMode
    ] = Field(
        default_factory=list
    )

    preferred_transport: list[
        TransportMode
    ] = Field(
        default_factory=list
    )

    max_transfers: int | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    hard_constraints: list[
        ConstraintField
    ] = Field(
        default_factory=list
    )


SYSTEM_PROMPT = """
Ты — специализированный parser пользовательских ограничений
для сервиса планирования поездок.

Твоя задача — преобразовать обычный текст пользователя
в структурированный запрос поездки.

Ты НЕ:
- ищешь билеты;
- ищешь отели;
- вызываешь Tutu;
- выбираешь маршрут;
- считаешь компромиссы;
- придумываешь цены.

После тебя работает deterministic Constraint Negotiator.


========================
ОСНОВНЫЕ ПОЛЯ
========================

origin:
город отправления.

destination:
город назначения.

outbound_date:
дата поездки туда.

return_date:
дата обратной поездки.


outbound_after:
самое раннее допустимое время отправления,
если пользователь его указал.

Примеры:

"после 19"
-> 19:00:00

"не раньше 18:30"
-> 18:30:00

Если конкретное время не указано,
оставь null.


return_before:
самое позднее допустимое время ПРИБЫТИЯ обратно.

Примеры:

"вернуться до 22"
-> 22:00:00

"дома надо быть не позже 23:30"
-> 23:30:00

Если время не указано:
-> null


travelers:
количество взрослых путешественников.

"я один"
-> 1

"вдвоём"
-> 2

"нас трое"
-> 3

Если количество не указано:
-> 1


budget:
общий бюджет ВСЕЙ поездки для ВСЕЙ группы.

Никогда не дели бюджет на количество людей.

"до 20 тысяч на двоих"
-> 20000

"30к максимум"
-> 30000

Если бюджет не указан:
-> null


========================
ТРАНСПОРТ
========================

Допустимые значения:

flight
train
bus
suburban_train


Соответствия:

самолёт
авиа
лететь
рейс
-> flight

поезд
жд
железная дорога
-> train

автобус
-> bus

электричка
-> suburban_train


excluded_transport:
транспорт, которым пользователь пользоваться не хочет.

"автобусы не люблю"
-> ["bus"]


preferred_transport:
предпочтительный транспорт.

"лучше поездом"
-> ["train"]

Если предпочтения нет:
-> []


max_transfers:
максимальное допустимое количество пересадок.

"без пересадок"
-> 0

"не больше одной пересадки"
-> 1

Если ограничения нет:
-> null


========================
SOFT / HARD
========================

hard_constraints содержит только ограничения,
которые пользователь ЯВНО запрещает нарушать.

Допустимые значения:

budget
outbound_after
return_before
transport
max_transfers


SOFT означает:
условие желательно,
но Constraint Negotiator может предложить его изменить.

Примеры SOFT:

"желательно до 20 тысяч"
"хотелось бы уложиться в 20к"
"автобусы не люблю"
"лучше без пересадок"
"желательно вернуться до 22"
"предпочтительно поездом"

Соответствующие поля заполни,
но hard_constraints НЕ добавляй.


HARD означает:
нарушать условие нельзя.

Примеры:

"больше 20 тысяч вообще никак"
"строго до 20 тысяч"
"20 тысяч — абсолютный потолок"
-> "budget"

"на автобусе точно не поеду"
"автобус исключён"
"никаких автобусов"
-> "transport"

"обязательно быть дома до 22"
"после 22 никак"
-> "return_before"

"раньше 19 физически не могу"
"строго после 19"
-> "outbound_after"

"никаких пересадок"
"пересадки исключены"
-> "max_transfers"


Не делай ограничение hard просто потому,
что пользователь сформулировал его уверенно.

Hard означает, что Negotiator НЕ ИМЕЕТ ПРАВА
предложить пользователю ослабить это ограничение.


========================
ДАТЫ
========================

Тебе передаётся REFERENCE_DATE.

Все относительные даты вычисляй относительно неё.

Например:

"завтра"
"послезавтра"
"в эти выходные"
"на следующих выходных"

Если пользователь указал точные даты,
используй их.


========================
ВАЖНО
========================

Не придумывай:
- бюджет;
- время;
- предпочтительный транспорт;
- запрещённый транспорт;
- количество пересадок.

Исключение:
если travelers не указан,
используй 1.

Не добавляй транспорт в excluded_transport,
если пользователь просто его не упомянул.

Верни только структурированные данные.
""".strip()


class TripParser:
    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        settings = get_settings()

        if settings.openai_api_key is None:
            raise RuntimeError(
                "OPENAI_API_KEY is required "
                "for natural-language trip parsing"
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
                ParsedTripSpec
            )
        )

    async def parse(
        self,
        message: str,
        reference_date: date,
    ) -> TripSpec:
        clean_message = (
            message.strip()
        )

        if not clean_message:
            raise ValueError(
                "Trip request cannot be empty"
            )

        prompt = f"""
REFERENCE_DATE:
{reference_date.isoformat()}

USER_REQUEST:
{clean_message}

Преобразуй запрос пользователя в структуру поездки.

Проверь перед ответом:

1. budget — общий бюджет всей группы.
2. soft constraints не попадают в hard_constraints.
3. hard_constraints только при явном абсолютном запрете.
4. return_before означает время прибытия обратно.
5. Не придумывай отсутствующие ограничения.
""".strip()

        result = (
            await self.structured_llm.ainvoke(
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
            ParsedTripSpec,
        ):
            result = (
                ParsedTripSpec.model_validate(
                    result
                )
            )

        payload = result.model_dump()

        # LLM DTO uses a list for OpenAI-compatible
        # JSON Schema.
        #
        # Domain model may continue using set.
        payload["hard_constraints"] = set(
            result.hard_constraints
        )

        return TripSpec.model_validate(
            payload
        )


@lru_cache(maxsize=1)
def get_trip_parser() -> TripParser:
    """
    Lazy singleton.

    /from-spec and MCP endpoints do not initialize
    the LLM. OpenAI is needed only when text parsing
    is actually requested.
    """

    return TripParser()