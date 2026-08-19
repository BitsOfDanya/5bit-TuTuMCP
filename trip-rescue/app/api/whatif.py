from __future__ import annotations

from datetime import date
from functools import lru_cache

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.api.mapper import (
    to_domain_journey,
)
from app.api.schemas import (
    CurrentJourneyInput,
)
from app.models.journey import (
    JourneyOption,
)
from app.models.trip import (
    TripSpec,
)
from app.whatif.engine import (
    WhatIfEngine,
)
from app.whatif.models import (
    WhatIfResult,
)
from app.whatif.presenter import (
    PublicWhatIfResponse,
    to_public_whatif_response,
)


router = APIRouter(
    prefix="/api/v1/what-if",
    tags=["what-if"],
)


class WhatIfFromTextRequest(
    BaseModel
):
    current_trip: TripSpec

    current_journey: JourneyOption

    message: str = Field(
        min_length=2,
        max_length=4000,
    )

    reference_date: (
        date
        | None
    ) = None


class WhatIfFromTextPublicRequest(
    BaseModel
):
    current_trip: TripSpec

    current_journey: (
        CurrentJourneyInput
    )

    message: str = Field(
        min_length=2,
        max_length=4000,
    )

    reference_date: (
        date
        | None
    ) = None


class WhatIfFromSpecRequest(
    BaseModel
):
    current_trip: TripSpec

    hypothetical_trip: TripSpec

    current_journey: JourneyOption


class WhatIfFromSpecPublicRequest(
    BaseModel
):
    current_trip: TripSpec

    hypothetical_trip: TripSpec

    current_journey: (
        CurrentJourneyInput
    )


@lru_cache(maxsize=1)
def get_whatif_engine() -> (
    WhatIfEngine
):
    return WhatIfEngine()


@router.post(
    "/from-text",
    response_model=WhatIfResult,
)
async def whatif_from_text(
    request: WhatIfFromTextRequest,
) -> WhatIfResult:
    try:
        engine = (
            get_whatif_engine()
        )

        return await (
            engine.simulate_from_text(
                current_trip=(
                    request.current_trip
                ),
                current_journey=(
                    request.current_journey
                ),
                message=(
                    request.message
                ),
                reference_date=(
                    request.reference_date
                    or date.today()
                ),
            )
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
                "Failed to simulate "
                "What-if scenario"
            ),
        ) from exc


@router.post(
    "/from-text/public",
    response_model=PublicWhatIfResponse,
)
async def whatif_from_text_public(
    request: (
        WhatIfFromTextPublicRequest
    ),
) -> PublicWhatIfResponse:
    try:
        journey = to_domain_journey(
            request.current_journey
        )

        engine = (
            get_whatif_engine()
        )

        result = await (
            engine.simulate_from_text(
                current_trip=(
                    request.current_trip
                ),
                current_journey=journey,
                message=(
                    request.message
                ),
                reference_date=(
                    request.reference_date
                    or date.today()
                ),
            )
        )

        return (
            to_public_whatif_response(
                result
            )
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
                "Failed to simulate "
                "What-if scenario"
            ),
        ) from exc


@router.post(
    "/from-spec",
    response_model=WhatIfResult,
)
async def whatif_from_spec(
    request: WhatIfFromSpecRequest,
) -> WhatIfResult:
    try:
        engine = (
            get_whatif_engine()
        )

        return await (
            engine.simulate_from_spec(
                current_trip=(
                    request.current_trip
                ),
                hypothetical_trip=(
                    request
                    .hypothetical_trip
                ),
                current_journey=(
                    request
                    .current_journey
                ),
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to simulate "
                "What-if scenario"
            ),
        ) from exc


@router.post(
    "/from-spec/public",
    response_model=PublicWhatIfResponse,
)
async def whatif_from_spec_public(
    request: (
        WhatIfFromSpecPublicRequest
    ),
) -> PublicWhatIfResponse:
    try:
        journey = to_domain_journey(
            request.current_journey
        )

        engine = (
            get_whatif_engine()
        )

        result = await (
            engine.simulate_from_spec(
                current_trip=(
                    request.current_trip
                ),
                hypothetical_trip=(
                    request
                    .hypothetical_trip
                ),
                current_journey=journey,
            )
        )

        return (
            to_public_whatif_response(
                result
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to simulate "
                "What-if scenario"
            ),
        ) from exc