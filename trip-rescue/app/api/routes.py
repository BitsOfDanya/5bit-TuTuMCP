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
    CandidatePersonalization,
    CurrentJourneyInput,
    PublicRescueResponse,
    RawRescueResponse,
    RescuePersonalizationSummary,
)
from app.explanations.rescue import (
    attach_rescue_explanations,
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
from app.preferences.scorer import (
    rerank_rescue_candidates,
)
from app.preferences.store import (
    get_preference_store,
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

    preference_profile_id: (
        str
        | None
    ) = Field(
        default=None,
        max_length=128,
    )


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

    preference_profile_id: (
        str
        | None
    ) = Field(
        default=None,
        max_length=128,
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

    return _to_personalized_public(
        result=result,
        profile_id=(
            request.preference_profile_id
        ),
        baseline_journey=journey,
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

    return _to_personalized_public(
        result=result,
        profile_id=(
            request.preference_profile_id
        ),
        baseline_journey=journey,
    )


def _to_personalized_public(
    *,
    result: RawRescueResponse,
    profile_id: str | None,
    baseline_journey: JourneyOption,
) -> PublicRescueResponse:

    clean_profile_id = (
        profile_id.strip()
        if profile_id
        else ""
    )

    # ---------------------------------------------------------
    # No preference profile
    # ---------------------------------------------------------

    if not clean_profile_id:
        public = (
            to_public_response(
                result
            )
        )

        return (
            attach_rescue_explanations(
                public=public,
                result=result,
                baseline_journey=(
                    baseline_journey
                ),
            )
        )

    # ---------------------------------------------------------
    # Resolve preference profile
    # ---------------------------------------------------------

    store = (
        get_preference_store()
    )

    profile = store.get(
        clean_profile_id
    )

    # ---------------------------------------------------------
    # Profile requested but not learned yet
    # ---------------------------------------------------------

    if profile is None:
        public = (
            to_public_response(
                result
            )
        )

        public.personalization = (
            RescuePersonalizationSummary(
                profile_id=(
                    clean_profile_id
                ),
                interactions=0,
                applied=False,
            )
        )

        return (
            attach_rescue_explanations(
                public=public,
                result=result,
                baseline_journey=(
                    baseline_journey
                ),
            )
        )

    # ---------------------------------------------------------
    # Nothing to rerank
    # ---------------------------------------------------------

    candidates = (
        result.execution.candidates
    )

    if not candidates:
        public = (
            to_public_response(
                result
            )
        )

        public.personalization = (
            RescuePersonalizationSummary(
                profile_id=(
                    profile.profile_id
                ),
                interactions=(
                    profile.interactions
                ),
                applied=False,
            )
        )

        return (
            attach_rescue_explanations(
                public=public,
                result=result,
                baseline_journey=(
                    baseline_journey
                ),
            )
        )

    # ---------------------------------------------------------
    # Personalized reranking
    # ---------------------------------------------------------

    ranked = (
        rerank_rescue_candidates(
            candidates=candidates,
            profile=profile,
        )
    )

    result.execution.candidates = [
        item.candidate
        for item
        in ranked
    ]

    public = (
        to_public_response(
            result
        )
    )

    metadata = {
        item.candidate.id: item
        for item
        in ranked
    }

    # ---------------------------------------------------------
    # Attach ranking metadata and preference reasons
    # ---------------------------------------------------------

    for candidate in (
        public.candidates
    ):
        item = metadata.get(
            candidate.id
        )

        if item is None:
            continue

        candidate.personalization = (
            CandidatePersonalization(
                preference_score=(
                    item.preference_score
                ),
                personalized_score=(
                    item.personalized_score
                ),
                rank_before=(
                    item.rank_before
                ),
                rank_after=(
                    item.rank_after
                ),
                reasons=list(
                    item.reasons
                ),
            )
        )

    public.personalization = (
        RescuePersonalizationSummary(
            profile_id=(
                profile.profile_id
            ),
            interactions=(
                profile.interactions
            ),
            applied=(
                profile.interactions
                > 0
            ),
        )
    )

    # ---------------------------------------------------------
    # Decision Explanation is intentionally attached LAST.
    #
    # At this point:
    # - domain ranking is final;
    # - personalization metadata exists;
    # - preference reasons exist;
    # - rescue insights exist;
    # - fallback relaxations exist.
    #
    # Explanation can therefore describe the complete
    # decision without changing any decision logic.
    # ---------------------------------------------------------

    return (
        attach_rescue_explanations(
            public=public,
            result=result,
            baseline_journey=(
                baseline_journey
            ),
        )
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