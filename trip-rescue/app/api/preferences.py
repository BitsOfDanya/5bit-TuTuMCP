from __future__ import annotations

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
from app.preferences.learner import (
    get_preference_learner,
)
from app.preferences.models import (
    PreferenceAction,
    PreferenceLearningResult,
    PreferenceProfile,
)
from app.preferences.scorer import (
    rerank_journeys,
)
from app.preferences.store import (
    get_preference_store,
)


router = APIRouter(
    prefix="/api/v1/preferences",
    tags=["preferences"],
)


class PreferenceFeedbackRequest(
    BaseModel
):
    profile_id: str = Field(
        min_length=1,
        max_length=128,
    )

    action: PreferenceAction

    candidate: CurrentJourneyInput

    shown_candidates: list[
        CurrentJourneyInput
    ] = Field(
        default_factory=list
    )


class PreferenceRerankRequest(
    BaseModel
):
    profile_id: str = Field(
        min_length=1,
        max_length=128,
    )

    candidates: list[
        CurrentJourneyInput
    ] = Field(
        min_length=1
    )


class PreferenceRerankItem(
    BaseModel
):
    candidate_id: str

    rank_before: int
    rank_after: int

    preference_score: float

    reasons: list[
        str
    ] = Field(
        default_factory=list
    )


class PreferenceRerankResponse(
    BaseModel
):
    profile_id: str

    interactions: int

    items: list[
        PreferenceRerankItem
    ]


class PreferenceResetResponse(
    BaseModel
):
    status: str
    profile_id: str


@router.post(
    "/feedback",
    response_model=(
        PreferenceLearningResult
    ),
)
async def preference_feedback(
    request: (
        PreferenceFeedbackRequest
    ),
) -> PreferenceLearningResult:

    candidate = (
        to_domain_journey(
            request.candidate
        )
    )

    shown = [
        to_domain_journey(
            value
        )
        for value
        in request.shown_candidates
    ]

    learner = (
        get_preference_learner()
    )

    try:
        return learner.learn(
            profile_id=(
                request.profile_id
            ),
            action=request.action,
            candidate=candidate,
            shown_candidates=shown,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/{profile_id}",
    response_model=(
        PreferenceProfile
    ),
)
async def get_profile(
    profile_id: str,
) -> PreferenceProfile:

    profile = (
        get_preference_store()
        .get(
            profile_id
        )
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Preference profile "
                "not found"
            ),
        )

    return profile


@router.delete(
    "/{profile_id}",
    response_model=(
        PreferenceResetResponse
    ),
)
async def reset_profile(
    profile_id: str,
) -> PreferenceResetResponse:

    store = (
        get_preference_store()
    )

    store.reset(
        profile_id
    )

    return PreferenceResetResponse(
        status="reset",
        profile_id=profile_id,
    )


@router.post(
    "/rerank",
    response_model=(
        PreferenceRerankResponse
    ),
)
async def rerank_preferences(
    request: (
        PreferenceRerankRequest
    ),
) -> PreferenceRerankResponse:

    store = (
        get_preference_store()
    )

    profile = store.get(
        request.profile_id
    )

    if profile is None:
        profile = (
            store.get_or_create(
                request.profile_id
            )
        )

    journeys = [
        to_domain_journey(
            value
        )
        for value
        in request.candidates
    ]

    ranked = rerank_journeys(
        journeys=journeys,
        profile=profile,
    )

    return (
        PreferenceRerankResponse(
            profile_id=(
                profile.profile_id
            ),
            interactions=(
                profile.interactions
            ),
            items=[
                PreferenceRerankItem(
                    candidate_id=(
                        item.journey.id
                    ),
                    rank_before=(
                        item.rank_before
                    ),
                    rank_after=(
                        item.rank_after
                    ),
                    preference_score=(
                        item.preference_score
                    ),
                    reasons=list(
                        item.reasons
                    ),
                )
                for item
                in ranked
            ],
        )
    )