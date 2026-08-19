from datetime import date
from json import JSONDecodeError, dumps, loads
from typing import Any

from langchain_core.messages import ToolMessage

from app.agent.prompts import PLANNER_PROMPT
from app.agent.search_options import build_search_options
from app.agent.state import TravelWorkflowState
from app.agent.tools.travel import (
    build_search_redirect,
    determine_next_action,
    merge_trip_details,
    validate_trip_details,
)
from app.domain.travel import AgentTurn, TravelPlan, TripDetails


class TravelWorkflowNodes:
    def __init__(self, planner: Any, executor: Any) -> None:
        self._planner = planner
        self._executor = executor

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

    def finalize(self, state: TravelWorkflowState) -> dict[str, Any]:
        turn = state["structured_response"]
        trip = merge_trip_details(state.get("current_trip", TripDetails()), turn.trip)
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
        return {
            "structured_response": AgentTurn(
                assistant_message=turn.assistant_message,
                trip=trip,
            ),
            "missing_fields": validation["missing_fields"],
            "next_action": next_action,
            "redirect_url": redirect_url,
            "tools_used": list(dict.fromkeys(tools_used)),
            "tool_statuses": state.get("tool_statuses", {}),
            "search_options": build_search_options(
                state.get("constraint_result"),
                redirect_url,
            ),
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
