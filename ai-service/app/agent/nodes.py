from datetime import date
from json import JSONDecodeError, dumps, loads
from typing import Any

from langchain_core.messages import ToolMessage

from app.agent.prompts import INTENT_CLASSIFIER_PROMPT, PLANNER_PROMPT
from app.agent.search_options import build_search_options
from app.agent.state import TravelWorkflowState
from app.agent.tools.travel import (
    build_search_redirect,
    determine_next_action,
    merge_trip_details,
    validate_trip_details,
)
from app.domain.travel import (
    AgentNextAction,
    AgentTurn,
    DecisionIntent,
    IntentClassification,
    PlanAction,
    PlanStep,
    TravelPlan,
    TripDetails,
)


class TravelWorkflowNodes:
    def __init__(
        self,
        planner: Any,
        executor: Any,
        search_client: Any | None = None,
        classifier: Any | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._search_client = search_client
        self._classifier = classifier

    async def classify(self, state: TravelWorkflowState) -> dict[str, DecisionIntent]:
        if self._classifier is None:
            return {"decision_intent": DecisionIntent.SEARCH}
        result = await self._classifier.ainvoke(
            [{"role": "system", "content": INTENT_CLASSIFIER_PROMPT}, *state["messages"]]
        )
        classification = IntentClassification.model_validate(result)
        return {"decision_intent": classification.intent}

    async def prepare_decision(self, state: TravelWorkflowState) -> dict[str, Any]:
        intent = state.get("decision_intent", DecisionIntent.SEARCH)
        current_trip = state.get("current_trip", TripDetails())
        messages = {
            DecisionIntent.PREFERENCES: (
                "Открою быструю настройку предпочтений: четыре выбора, после которых "
                "варианты будут ранжироваться персонально."
            ),
            DecisionIntent.GROUP_PREFERENCES: (
                "Соберём профили участников и найдём групповой компромисс с конфликтами "
                "и общим рейтингом вариантов."
            ),
            DecisionIntent.RESCUE: (
                "Проверю принятую поездку и постараюсь заменить только сломанную часть, "
                "сохранив остальные бронирования."
            ),
            DecisionIntent.WHAT_IF: (
                "Запущу отдельную what-if симуляцию. Текущая принятая поездка не изменится."
            ),
        }
        plan = TravelPlan(
            objective="Открыть подходящий сценарий Decision Intelligence.",
            steps=[
                PlanStep(action=PlanAction.EXTRACT_TRIP_DETAILS, reason="Определить контекст."),
                PlanStep(action=PlanAction.VALIDATE_TRIP_DETAILS, reason="Проверить сценарий."),
                PlanStep(action=PlanAction.DETERMINE_NEXT_ACTION, reason="Открыть decision flow."),
            ],
        )
        return {
            "structured_response": AgentTurn(
                assistant_message=messages[intent],
                trip=current_trip,
                decision_intent=intent,
            ),
            "plan": plan,
            "missing_fields": [],
            "next_action": AgentNextAction.DECISION_SUPPORT.value,
            "redirect_url": None,
            "tools_used": [],
            "tool_statuses": {},
            "search_options": [],
        }

    async def plan(self, state: TravelWorkflowState) -> dict[str, TravelPlan]:
        current_trip = state.get("current_trip", TripDetails())
        plan = await self._planner.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        f"{PLANNER_PROMPT}\n\nCurrent date: {date.today().isoformat()}. "
                        "Current trip state: "
                        f"{dumps(current_trip.model_dump(mode='json'), ensure_ascii=False)}"
                    ),
                },
                *state["messages"],
            ]
        )
        return {"plan": TravelPlan.model_validate(plan)}

    async def execute(self, state: TravelWorkflowState) -> dict[str, Any]:
        current_trip = state.get("current_trip", TripDetails())
        execution_context = {
            "role": "system",
            "content": (
                f"Current date: {date.today().isoformat()}. Current normalized trip state: "
                f"{dumps(current_trip.model_dump(mode='json'), ensure_ascii=False)}. "
                "Execute this plan: "
                f"{dumps(state['plan'].model_dump(mode='json'), ensure_ascii=False)}"
            ),
        }
        result = await self._executor.ainvoke({"messages": [execution_context, *state["messages"]]})
        turn = AgentTurn.model_validate(result["structured_response"])
        tools_used = [
            message.name
            for message in result.get("messages", [])
            if isinstance(message, ToolMessage) and message.name
        ]
        tool_payloads = tool_payloads_from_messages(result.get("messages", []))
        return {
            "structured_response": turn,
            "tools_used": tools_used,
            "tool_statuses": tool_statuses_from_payloads(tool_payloads),
            "constraint_result": tool_payloads.get("negotiate_constraints", {}),
        }

    async def finalize(self, state: TravelWorkflowState) -> dict[str, Any]:
        turn = state["structured_response"]
        trip = merge_trip_details(state.get("current_trip", TripDetails()), turn.trip)
        if turn.decision_intent is not DecisionIntent.SEARCH:
            return {
                "structured_response": AgentTurn(
                    assistant_message=turn.assistant_message,
                    trip=trip,
                    decision_intent=turn.decision_intent,
                ),
                "missing_fields": [],
                "next_action": AgentNextAction.DECISION_SUPPORT.value,
                "redirect_url": None,
                "tools_used": list(dict.fromkeys(state.get("tools_used", []))),
                "tool_statuses": state.get("tool_statuses", {}),
                "search_options": [],
            }
        tool_input = {"trip": trip.model_dump(mode="json")}
        validation = validate_trip_details.invoke(tool_input)
        next_action = determine_next_action.invoke(tool_input)["next_action"]
        redirect_url = None
        tools_used = [
            *state.get("tools_used", []),
            validate_trip_details.name,
            determine_next_action.name,
        ]
        if next_action == "redirect_to_search":
            redirect_url = build_search_redirect.invoke(tool_input)["redirect_url"]
            tools_used.append(build_search_redirect.name)
        constraint_result = state.get("constraint_result") or {}
        if (
            not validation["missing_fields"]
            and self._search_client is not None
            and not constraint_result.get("options")
        ):
            constraint_result = await self._search_client.negotiate(trip)
            tools_used.append("search_travel_options")

        tool_statuses = state.get("tool_statuses", {})
        if constraint_result:
            tool_statuses = {
                **tool_statuses,
                "search_travel_options": str(constraint_result.get("status", "unknown")),
            }

        return {
            "structured_response": AgentTurn(
                assistant_message=turn.assistant_message,
                trip=trip,
                decision_intent=turn.decision_intent,
            ),
            "missing_fields": validation["missing_fields"],
            "next_action": next_action,
            "redirect_url": redirect_url,
            "tools_used": list(dict.fromkeys(tools_used)),
            "tool_statuses": tool_statuses,
            "search_options": build_search_options(constraint_result, redirect_url),
        }


def tool_payloads_from_messages(messages: list[Any]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for message in messages:
        if not isinstance(message, ToolMessage) or not message.name:
            continue
        payload: Any = message.content
        if isinstance(payload, str):
            try:
                payload = loads(payload)
            except JSONDecodeError:
                continue
        if isinstance(payload, dict):
            payloads[message.name] = payload
    return payloads


def tool_statuses_from_payloads(payloads: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        name: payload["status"]
        for name, payload in payloads.items()
        if isinstance(payload.get("status"), str)
    }
