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

from app.ai.parser import (
    get_trip_update_parser,
)
from app.api.mapper import (
    to_domain_journey,
    to_public_response,
)
from app.api.schemas import (
    CurrentJourneyInput,
    PublicRescueResponse,
    RawRescueResponse,
)
from app.graph.builder import (
    rescue_graph,
)
from app.models.journey import (
    JourneyOption,
)
from app.models.trip import (
    TripSpec,
)


router = APIRouter(
    prefix="/api/v1/rescue",
    tags=["rescue"],
)


class ParseUpdateRequest(BaseModel):
    current_trip: TripSpec

    message: str = Field(
        min_length=2,
        max_length=4000,
    )

    reference_date: date | None = None


class FromTextRequest(BaseModel):
    current_trip: TripSpec

    current_journey: JourneyOption

    message: str = Field(
        min_length=2,
        max_length=4000,
    )

    reference_date: date | None = None


class FromTextPublicRequest(BaseModel):
    current_trip: TripSpec

    current_journey: (
        CurrentJourneyInput
    )

    message: str = Field(
        min_length=2,
        max_length=4000,
    )

    reference_date: date | None = None


class FromSpecRequest(BaseModel):
    current_trip: TripSpec
    updated_trip: TripSpec

    current_journey: JourneyOption


class FromSpecPublicRequest(BaseModel):
    current_trip: TripSpec
    updated_trip: TripSpec

    current_journey: (
        CurrentJourneyInput
    )


@router.post(
    "/parse-update",
    response_model=TripSpec,
)
async def parse_update(
    request: ParseUpdateRequest,
) -> TripSpec:
    try:
        parser = (
            get_trip_update_parser()
        )

        return await parser.parse(
            previous_trip=(
                request.current_trip
            ),
            message=request.message,
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

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to parse "
                "trip update"
            ),
        ) from exc


@router.post(
    "/from-text",
    response_model=RawRescueResponse,
)
async def rescue_from_text(
    request: FromTextRequest,
) -> RawRescueResponse:
    return await _run_graph(
        current_trip=(
            request.current_trip
        ),
        current_journey=(
            request.current_journey
        ),
        request_text=(
            request.message
        ),
        reference_date=(
            request.reference_date
        ),
    )


@router.post(
    "/from-text/public",
    response_model=PublicRescueResponse,
)
async def rescue_from_text_public(
    request: FromTextPublicRequest,
) -> PublicRescueResponse:
    journey = to_domain_journey(
        request.current_journey
    )

    result = await _run_graph(
        current_trip=(
            request.current_trip
        ),
        current_journey=journey,
        request_text=(
            request.message
        ),
        reference_date=(
            request.reference_date
        ),
    )

    return to_public_response(
        result
    )


@router.post(
    "/from-spec",
    response_model=RawRescueResponse,
)
async def rescue_from_spec(
    request: FromSpecRequest,
) -> RawRescueResponse:
    return await _run_graph(
        current_trip=(
            request.current_trip
        ),
        current_journey=(
            request.current_journey
        ),
        updated_trip=(
            request.updated_trip
        ),
    )


@router.post(
    "/from-spec/public",
    response_model=PublicRescueResponse,
)
async def rescue_from_spec_public(
    request: FromSpecPublicRequest,
) -> PublicRescueResponse:
    journey = to_domain_journey(
        request.current_journey
    )

    result = await _run_graph(
        current_trip=(
            request.current_trip
        ),
        current_journey=journey,
        updated_trip=(
            request.updated_trip
        ),
    )

    return to_public_response(
        result
    )


async def _run_graph(
    *,
    current_trip: TripSpec,
    current_journey: JourneyOption,
    request_text: str | None = None,
    reference_date: date | None = None,
    updated_trip: TripSpec | None = None,
) -> RawRescueResponse:
    state = {
        "previous_trip": (
            current_trip.model_dump(
                mode="json"
            )
        ),
        "current_journey": (
            current_journey.model_dump(
                mode="json"
            )
        ),
    }

    if request_text is not None:
        state[
            "request_text"
        ] = request_text

        state[
            "reference_date"
        ] = (
            reference_date
            or date.today()
        ).isoformat()

    if updated_trip is not None:
        state[
            "updated_trip"
        ] = (
            updated_trip.model_dump(
                mode="json"
            )
        )

    try:
        graph_result = (
            await rescue_graph.ainvoke(
                state
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Trip Rescue execution failed"
            ),
        ) from exc

    return (
        RawRescueResponse
        .model_validate(
            graph_result["result"]
        )
    )