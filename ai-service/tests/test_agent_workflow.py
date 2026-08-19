from datetime import date, time
from typing import Any

import pytest
from langchain_core.messages import ToolMessage

from app.agent.graph import build_travel_workflow
from app.domain.travel import (
    AgentTurn,
    PlanAction,
    PlanStep,
    TravelPlan,
    TravelService,
    TripDetails,
)


class FakePlanner:
    async def ainvoke(self, _: list[Any]) -> TravelPlan:
        return TravelPlan(
            objective="Дополнить поездку и подготовить поиск.",
            steps=[
                PlanStep(action=PlanAction.EXTRACT_TRIP_DETAILS, reason="Извлечь."),
                PlanStep(action=PlanAction.VALIDATE_TRIP_DETAILS, reason="Проверить."),
                PlanStep(action=PlanAction.DETERMINE_NEXT_ACTION, reason="Выбрать этап."),
                PlanStep(action=PlanAction.BUILD_SEARCH_REDIRECT, reason="Собрать URL."),
            ],
        )


class FakeExecutor:
    async def ainvoke(self, _: dict[str, Any]) -> dict[str, Any]:
        return {
            "structured_response": AgentTurn(
                assistant_message="**Все параметры собраны.**",
                trip=TripDetails(
                    start_date=date(2026, 9, 1),
                    preferred_time=time(10, 30),
                    passengers=2,
                    budget=20_000,
                ),
            ),
            "messages": [
                ToolMessage(
                    content="validated",
                    tool_call_id="call-1",
                    name="validate_trip_details",
                )
            ],
        }


@pytest.mark.asyncio
async def test_plan_execute_workflow_merges_state_and_runs_tools() -> None:
    workflow = build_travel_workflow(FakePlanner(), FakeExecutor())
    result = await workflow.ainvoke(
        {
            "messages": [{"role": "user", "content": "1 сентября, двое"}],
            "current_trip": TripDetails(
                service_type=TravelService.TRAIN,
                origin="Москва",
                destination="Казань",
            ),
        }
    )
    assert result["structured_response"].trip.origin == "Москва"
    assert result["missing_fields"] == []
    assert result["next_action"] == "redirect_to_search"
    assert result["redirect_url"].startswith("/search/train?")
    assert result["tools_used"] == [
        "validate_trip_details",
        "determine_next_action",
        "build_search_redirect",
    ]


def test_plan_allows_negotiation_before_redirect() -> None:
    plan = TravelPlan(
        objective="Найти варианты и ослабления ограничений.",
        steps=[
            PlanStep(action=PlanAction.EXTRACT_TRIP_DETAILS, reason="Извлечь."),
            PlanStep(action=PlanAction.VALIDATE_TRIP_DETAILS, reason="Проверить."),
            PlanStep(action=PlanAction.DETERMINE_NEXT_ACTION, reason="Выбрать этап."),
            PlanStep(action=PlanAction.NEGOTIATE_CONSTRAINTS, reason="Найти варианты."),
            PlanStep(action=PlanAction.BUILD_SEARCH_REDIRECT, reason="Собрать URL."),
        ],
    )
    assert plan.steps[-2].action is PlanAction.NEGOTIATE_CONSTRAINTS
