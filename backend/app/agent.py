from datetime import date
from functools import lru_cache
from json import dumps
from typing import Any, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.schemas import AgentTurn, TravelPlan, TravelService, TripDetails
from app.travel_tools import (
    TRAVEL_TOOLS,
    build_search_redirect,
    determine_next_action,
    validate_trip_details,
)

PLANNER_PROMPT = """
You are the planner for a tutu.ru travel intake workflow. Produce a short executable plan
for the latest user turn. Use only these actions: extract_trip_details,
validate_trip_details, determine_next_action, build_search_redirect.

Every plan must first extract or update trip details, then validate them, then determine
the next action. Include build_search_redirect only when the available conversation likely
contains all required trip fields. Do not answer the user and do not invent search results.
""".strip()

EXECUTOR_PROMPT = """
You are the executor for a tutu.ru travel intake plan. Speak Russian unless the user asks
for another language. Follow the supplied plan and use the available tools when relevant.
Your task is to collect and normalize parameters, never to invent tickets, hotels, prices,
or search results.

Map railway/train to train, airplane/flight to flight, bus to bus, and hotel to hotel.
Preserve existing facts and apply explicit corrections from the latest user message. Never
guess unknown values. Resolve relative dates from the current date supplied at runtime.

For transport collect origin, destination, start date, preferred departure time, total
passengers, and maximum total budget. A return date is optional. For hotels collect the
destination, check-in and check-out dates, total guests, and maximum total budget; origin
and preferred time are optional. Default currency to RUB only when unspecified.

For flights determine whether the route crosses a national border. Use true for an
international flight, false for a domestic flight, and null when unclear. For non-flight
services leave is_international null.

Return every known value in trip and null for unknown values. Briefly confirm newly
understood details and ask for at most two next missing fields. If the trip is complete and
international, tell the user that passenger documents are the next step. Do not claim a
search or redirect happened.
""".strip()


class TravelWorkflowState(TypedDict, total=False):
    messages: list[Any]
    current_trip: TripDetails
    plan: TravelPlan
    structured_response: AgentTurn
    tools_used: list[str]
    missing_fields: list[str]
    next_action: str
    redirect_url: str | None


def build_travel_workflow(planner: Any, executor: Any) -> Any:
    async def plan_node(state: TravelWorkflowState) -> dict[str, TravelPlan]:
        current_trip = state.get("current_trip", TripDetails())
        plan = await planner.ainvoke(
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

    async def execute_node(state: TravelWorkflowState) -> dict[str, Any]:
        current_trip = state.get("current_trip", TripDetails())
        execution_context = {
            "role": "system",
            "content": (
                f"Current date: {date.today().isoformat()}. "
                "Current normalized trip state: "
                f"{dumps(current_trip.model_dump(mode='json'), ensure_ascii=False)}. "
                "Execute this plan: "
                f"{dumps(state['plan'].model_dump(mode='json'), ensure_ascii=False)}"
            ),
        }
        result = await executor.ainvoke(
            {"messages": [execution_context, *state["messages"]]}
        )
        turn = AgentTurn.model_validate(result["structured_response"])
        tools_used = [
            message.name
            for message in result.get("messages", [])
            if isinstance(message, ToolMessage) and message.name
        ]
        return {"structured_response": turn, "tools_used": tools_used}

    def finalize_node(state: TravelWorkflowState) -> dict[str, Any]:
        turn = state["structured_response"]
        trip = merge_trip_details(state.get("current_trip", TripDetails()), turn.trip)
        tool_input = {"trip": trip}

        validation = validate_trip_details.invoke(tool_input)
        action_result = determine_next_action.invoke(tool_input)
        next_action = action_result["next_action"]
        redirect_url = None
        tools_used = [
            *state.get("tools_used", []),
            validate_trip_details.name,
            determine_next_action.name,
        ]

        if next_action == "redirect_to_search":
            redirect_result = build_search_redirect.invoke(tool_input)
            redirect_url = redirect_result["redirect_url"]
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
        }

    graph = StateGraph(TravelWorkflowState)
    graph.add_node("planner", plan_node)
    graph.add_node("executor", execute_node)
    graph.add_node("finalizer", finalize_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "finalizer")
    graph.add_edge("finalizer", END)
    return graph.compile()


@lru_cache
def get_agent() -> Any:
    """Build the process-wide plan-and-execute travel workflow."""
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key.get_secret_value(),
    )
    planner = model.with_structured_output(TravelPlan)
    executor = create_agent(
        model=model,
        tools=TRAVEL_TOOLS,
        system_prompt=f"{EXECUTOR_PROMPT}\n\n{settings.agent_system_prompt}",
        response_format=AgentTurn,
    )
    return build_travel_workflow(planner, executor)


def merge_trip_details(current: TripDetails, extracted: TripDetails) -> TripDetails:
    values = current.model_dump()
    values.update(extracted.model_dump(exclude_none=True))

    if values["service_type"] is TravelService.HOTEL:
        values["origin"] = None
        values["is_international"] = None
    elif values["service_type"] is not TravelService.FLIGHT:
        values["is_international"] = None

    return TripDetails.model_validate(values)
