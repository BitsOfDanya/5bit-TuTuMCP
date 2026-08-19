from functools import lru_cache
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import TravelWorkflowNodes
from app.agent.prompts import EXECUTOR_PROMPT
from app.agent.state import TravelWorkflowState
from app.agent.tools.registry import build_travel_tools
from app.core.config import get_settings
from app.domain.travel import AgentTurn, TravelPlan
from app.integrations.constraint_negotiator.client import get_constraint_negotiator_client
from app.integrations.smart_trip_tracker.client import get_smart_trip_tracker_client


def build_travel_workflow(planner: Any, executor: Any, search_client: Any | None = None) -> Any:
    nodes = TravelWorkflowNodes(planner, executor, search_client)
    graph = StateGraph(TravelWorkflowState)
    graph.add_node("planner", nodes.plan)
    graph.add_node("executor", nodes.execute)
    graph.add_node("finalizer", nodes.finalize)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "finalizer")
    graph.add_edge("finalizer", END)
    return graph.compile()


@lru_cache
def get_agent() -> Any:
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key.get_secret_value(),
        reasoning_effort=settings.openai_reasoning_effort,
    )
    negotiator = get_constraint_negotiator_client()
    tracker = get_smart_trip_tracker_client()
    planner = model.with_structured_output(TravelPlan)
    executor = create_agent(
        model=model,
        tools=build_travel_tools(negotiator, tracker),
        system_prompt=f"{EXECUTOR_PROMPT}\n\n{settings.agent_system_prompt}",
        response_format=AgentTurn,
    )
    return build_travel_workflow(planner, executor, negotiator)
