from datetime import date, time
from typing import Any

import pytest
from langchain_core.messages import ToolMessage

from app.agent import build_travel_workflow
from app.schemas import (
    AgentTurn,
    PlanAction,
    PlanStep,
    TravelPlan,
    TravelService,
    TripDetails,
)


class FakePlanner:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    async def ainvoke(self, messages: list[Any]) -> TravelPlan:
        self.messages = messages
        return TravelPlan(
            objective="Дополнить поездку и подготовить переход к поиску.",
            steps=[
                PlanStep(action=PlanAction.EXTRACT_TRIP_DETAILS, reason="Извлечь данные."),
                PlanStep(action=PlanAction.VALIDATE_TRIP_DETAILS, reason="Проверить поля."),
                PlanStep(action=PlanAction.DETERMINE_NEXT_ACTION, reason="Выбрать этап."),
                PlanStep(action=PlanAction.BUILD_SEARCH_REDIRECT, reason="Собрать URL."),
            ],
        )


class FakeExecutor:
    def __init__(self) -> None:
        self.payload: dict[str, Any] = {}

    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payload = payload
        return {
            "structured_response": AgentTurn(
                assistant_message="Все параметры собраны.",
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
    planner = FakePlanner()
    executor = FakeExecutor()
    workflow = build_travel_workflow(planner, executor)
    current_trip = TripDetails(
        service_type=TravelService.TRAIN,
        origin="Москва",
        destination="Казань",
    )

    result = await workflow.ainvoke(
        {
            "messages": [{"role": "user", "content": "1 сентября, двое, 20 тысяч"}],
            "current_trip": current_trip,
        }
    )

    assert result["plan"].steps[-1].action is PlanAction.BUILD_SEARCH_REDIRECT
    assert result["structured_response"].trip.origin == "Москва"
    assert result["structured_response"].trip.start_date == date(2026, 9, 1)
    assert result["missing_fields"] == []
    assert result["next_action"] == "redirect_to_search"
    assert result["redirect_url"].startswith("/search/train?")
    assert result["tools_used"] == [
        "validate_trip_details",
        "determine_next_action",
        "build_search_redirect",
    ]
    assert "Execute this plan" in executor.payload["messages"][0]["content"]
    assert planner.messages[-1]["content"] == "1 сентября, двое, 20 тысяч"


def test_plan_rejects_invalid_execution_order() -> None:
    with pytest.raises(ValueError, match="must start with"):
        TravelPlan(
            objective="Неверный план",
            steps=[
                PlanStep(action=PlanAction.VALIDATE_TRIP_DETAILS, reason="Слишком рано."),
                PlanStep(action=PlanAction.EXTRACT_TRIP_DETAILS, reason="Поздно."),
                PlanStep(action=PlanAction.DETERMINE_NEXT_ACTION, reason="Этап."),
            ],
        )
