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
    get_trip_parser,
)
from app.api.mapper import (
    attach_checkout_links,
    to_public_result,
)
from app.api.schemas import (
    ProductSearchRequest,
    PublicNegotiationResult,
    PublicProductSearchResult,
)
from app.graph.builder import (
    negotiator_graph,
)
from app.models.relaxation import (
    NegotiationResult,
)
from app.models.trip import (
    TripSpec,
)
from app.search.products import ProductSearchService


router = APIRouter(
    prefix="/api/v1/negotiator",
    tags=["negotiator"],
)

product_search = ProductSearchService()


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

    try:
        parser = (
            get_trip_parser()
        )

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

    result = await _run_from_spec(
        request.trip
    )

    return result


@router.post(
    "/from-text",
    response_model=NegotiationResult,
)
async def negotiate_from_text(
    request: FromTextRequest,
) -> NegotiationResult:

    return await _run_from_text(
        request
    )


# ---------------------------------------------------------
# PUBLIC / FRONTEND API
# ---------------------------------------------------------


@router.post(
    "/from-spec/public",
    response_model=(
        PublicNegotiationResult
    ),
)
async def negotiate_from_spec_public(
    request: FromSpecRequest,
) -> PublicNegotiationResult:

    result = await _run_from_spec(
        request.trip
    )

    public = to_public_result(result)
    return await attach_checkout_links(public, result)


@router.post(
    "/from-text/public",
    response_model=(
        PublicNegotiationResult
    ),
)
async def negotiate_from_text_public(
    request: FromTextRequest,
) -> PublicNegotiationResult:

    result = await _run_from_text(request)
    public = to_public_result(result)
    return await attach_checkout_links(public, result)


@router.post(
    "/products/search",
    response_model=PublicProductSearchResult,
)
async def search_products(
    request: ProductSearchRequest,
) -> PublicProductSearchResult:
    try:
        return await product_search.search(request)
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


# ---------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------


async def _run_from_spec(
    trip: TripSpec,
) -> NegotiationResult:

    state = (
        await negotiator_graph.ainvoke(
            {
                "trip_spec": (
                    trip.model_dump(
                        mode="json"
                    )
                )
            }
        )
    )

    return (
        NegotiationResult
        .model_validate(
            state["result"]
        )
    )


async def _run_from_text(
    request: FromTextRequest,
) -> NegotiationResult:

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
                        )
                        .isoformat()
                    ),
                }
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return (
        NegotiationResult
        .model_validate(
            state["result"]
        )
    )
