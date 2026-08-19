from __future__ import annotations

from datetime import date

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.ai.parser import get_trip_parser
from app.graph.builder import (
    negotiator_graph,
)
from app.models.relaxation import (
    NegotiationResult,
)
from app.models.trip import TripSpec


router = APIRouter(
    prefix="/api/v1/negotiator",
    tags=["negotiator"],
)


class FromSpecRequest(BaseModel):
    trip: TripSpec


class FromTextRequest(BaseModel):
    text: str = Field(
        min_length=3,
        max_length=4000,
    )

    reference_date: date | None = None


class ParseTextRequest(BaseModel):
    text: str = Field(
        min_length=3,
        max_length=4000,
    )

    reference_date: date | None = None


@router.post(
    "/parse",
    response_model=TripSpec,
)
async def parse_trip_text(
    request: ParseTextRequest,
) -> TripSpec:
    """
    Debug/demo endpoint.

    Only:
        natural language -> TripSpec

    Does NOT call Tutu MCP.
    """

    try:
        parser = get_trip_parser()

        return await parser.parse(
            message=request.text,
            reference_date=(
                request.reference_date
                or date.today()
            ),
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post(
    "/from-spec",
    response_model=NegotiationResult,
)
async def negotiate_from_spec(
    request: FromSpecRequest,
) -> NegotiationResult:
    """
    Structured TripSpec -> Tutu -> Negotiator.

    LLM is NOT used.
    """

    state = await negotiator_graph.ainvoke(
        {
            "trip_spec": (
                request.trip.model_dump(
                    mode="json"
                )
            )
        }
    )

    return NegotiationResult.model_validate(
        state["result"]
    )


@router.post(
    "/from-text",
    response_model=NegotiationResult,
)
async def negotiate_from_text(
    request: FromTextRequest,
) -> NegotiationResult:
    """
    Natural language
        -> TripSpec
        -> Tutu MCP
        -> hotel
        -> Constraint Negotiator.
    """

    try:
        state = (
            await negotiator_graph.ainvoke(
                {
                    "request_text": (
                        request.text
                    ),
                    "reference_date": (
                        (
                            request.reference_date
                            or date.today()
                        ).isoformat()
                    ),
                }
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return NegotiationResult.model_validate(
        state["result"]
    )