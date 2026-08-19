from datetime import datetime
from functools import lru_cache
from json import dumps
from typing import Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.domain.booking import (
    BookingCopilotDecision,
    BookingCopilotRequest,
    BookingCopilotResponse,
    BookingStep,
)

SYSTEM_PROMPT = """You are Jarvell, a careful travel checkout copilot.
Return Russian Markdown and a structured proposal for exactly the current booking step.

Rules:
- Use only facts explicitly present in the trip, conversation, instruction, current options,
  or previous selections. Never invent names, birth dates, document numbers, or preferences.
- For a single-choice step, choose exactly one available option id.
- For extras, choose only explicitly requested services and ALWAYS copy their exact ids into
  option_ids. An empty list is valid only when no extra is requested.
- For seats, choose the required number of available seats and prefer adjacent seats.
- For passenger, document, or guest data, copy only explicitly provided values and list every
  missing field. Preserve document numbers exactly except for removing spaces.
- Never approve a fare, order, payment, or checkout on the user's behalf.
- If the current step is confirmation or checkout, explain what the user must verify and return
  no proposal fields.
- Keep the message concise and explain why the proposal is safe or what is still missing.
"""


class BookingCopilotState(TypedDict, total=False):
    request: BookingCopilotRequest
    raw_decision: BookingCopilotDecision
    response: BookingCopilotResponse


class BookingCopilotNodes:
    def __init__(self, model: Any) -> None:
        self._model = model

    async def propose(self, state: BookingCopilotState) -> dict[str, BookingCopilotDecision]:
        request = state["request"]
        decision = await self._model.ainvoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": dumps(request.model_dump(mode="json"), ensure_ascii=False),
                },
            ]
        )
        return {"raw_decision": BookingCopilotDecision.model_validate(decision)}

    async def guard(self, state: BookingCopilotState) -> dict[str, BookingCopilotResponse]:
        return {"response": normalize_decision(state["request"], state["raw_decision"])}


def build_booking_copilot(model: Any) -> Any:
    nodes = BookingCopilotNodes(model)
    graph = StateGraph(BookingCopilotState)
    graph.add_node("propose", nodes.propose)
    graph.add_node("guard", nodes.guard)
    graph.add_edge(START, "propose")
    graph.add_edge("propose", "guard")
    graph.add_edge("guard", END)
    return graph.compile()


def normalize_decision(
    request: BookingCopilotRequest,
    decision: BookingCopilotDecision,
) -> BookingCopilotResponse:
    available = {option.id for option in request.current_options if option.available}
    proposed_data: dict[str, Any] = {}
    missing = list(dict.fromkeys(decision.missing_fields))
    step = request.current_step

    if step in {
        BookingStep.SELECT_CARRIAGE,
        BookingStep.SELECT_ROOM,
        BookingStep.SELECT_FARE,
    }:
        if decision.option_id in available:
            proposed_data = {"option_id": decision.option_id}
        else:
            missing.append("option_id")
    elif step is BookingStep.SELECT_EXTRAS:
        option_ids = [item for item in decision.option_ids if item in available]
        if not option_ids and request.instruction:
            instruction = request.instruction.casefold()
            option_ids = [
                option.id
                for option in request.current_options
                if option.available and explicitly_requested(option.title, instruction)
            ]
        proposed_data = {"option_ids": option_ids}
    elif step is BookingStep.SELECT_SEATS:
        seats = list(dict.fromkeys(item for item in decision.seat_ids if item in available))
        if len(seats) == request.travelers_count:
            proposed_data = {"seat_ids": seats}
        else:
            missing.append("seat_ids")
    elif step in {BookingStep.PASSENGERS, BookingStep.DOCUMENTS, BookingStep.GUESTS}:
        travelers = []
        for traveler in decision.travelers:
            traveler_data = traveler.model_dump(exclude_none=True)
            birth_date = traveler_data.get("birth_date")
            if isinstance(birth_date, str):
                normalized_birth_date = normalize_birth_date(birth_date)
                if normalized_birth_date is None:
                    traveler_data.pop("birth_date")
                    missing.append("birth_date")
                else:
                    traveler_data["birth_date"] = normalized_birth_date
            travelers.append(traveler_data)
        if travelers:
            proposed_data = {"travelers": travelers[: request.travelers_count]}
        if len(travelers) < request.travelers_count:
            missing.append("travelers")

    missing = list(dict.fromkeys(missing))
    return BookingCopilotResponse(
        assistant_message=decision.assistant_message,
        proposed_data=proposed_data,
        missing_fields=missing,
        can_apply=bool(proposed_data),
        requires_user_confirmation=True,
    )


def explicitly_requested(title: str, instruction: str) -> bool:
    normalized_title = title.casefold()
    index = instruction.find(normalized_title)
    if index < 0:
        return False
    prefix = instruction[max(0, index - 8) : index].strip(" ,.;:")
    suffix = instruction[index + len(normalized_title) :].lstrip(" ,.;:")
    return not prefix.endswith("без") and not suffix.startswith(("не нуж", "не добав"))


def normalize_birth_date(value: str) -> str | None:
    normalized = value.strip()
    for date_format in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None


@lru_cache
def get_booking_copilot() -> Any:
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key.get_secret_value(),
        reasoning_effort=settings.openai_reasoning_effort,
    ).with_structured_output(BookingCopilotDecision)
    return build_booking_copilot(model)
