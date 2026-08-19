from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.graph.builder import negotiator_graph
from app.models.relaxation import NegotiationResult
from app.models.trip import TripSpec


router = APIRouter(
    prefix="/api/v1/negotiator",
    tags=["constraint-negotiator"],
)


class TextNegotiationRequest(BaseModel):
    message: str = Field(
        min_length=3,
        max_length=3000,
    )

    reference_date: date | None = None


class SpecNegotiationRequest(BaseModel):
    trip: TripSpec


@router.post(
    "/from-text",
    response_model=NegotiationResult,
)
async def negotiate_from_text(
    payload: TextNegotiationRequest,
) -> NegotiationResult:

    state = await negotiator_graph.ainvoke(
        {
            "request_text": payload.message,
            "reference_date": (
                payload.reference_date.isoformat()
                if payload.reference_date
                else date.today().isoformat()
            ),
        }
    )

    return NegotiationResult.model_validate(
        state["result"]
    )


@router.post(
    "/from-spec",
    response_model=NegotiationResult,
)
async def negotiate_from_spec(
    payload: SpecNegotiationRequest,
) -> NegotiationResult:

    state = await negotiator_graph.ainvoke(
        {
            "trip_spec": payload.trip.model_dump(
                mode="json"
            )
        }
    )

    return NegotiationResult.model_validate(
        state["result"]
    )