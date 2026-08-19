from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
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
from app.preferences.cold_start import (
    ColdStartChoice,
    ColdStartQuestion,
    get_cold_start_questions,
)
from app.preferences.cold_start_service import (
    ColdStartCompletion,
    ColdStartService,
)
from app.preferences.group import (
    GroupPreferenceSummary,
)
from app.preferences.group_service import (
    GroupRerankResult,
    MissingGroupProfilesError,
    get_group_preference_service,
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


class ColdStartQuestionsResponse(
    BaseModel
):
    total: int

    minimum_choices: int = 4

    questions: list[
        ColdStartQuestion
    ]


class ColdStartCompleteRequest(
    BaseModel
):
    profile_id: str = Field(
        min_length=1,
        max_length=128,
    )

    choices: list[
        ColdStartChoice
    ] = Field(
        min_length=1,
        max_length=6,
    )

    replace: bool = False


class GroupProfileRequest(
    BaseModel
):
    group_id: str = Field(
        min_length=1,
        max_length=128,
    )

    profile_ids: list[
        str
    ] = Field(
        min_length=2,
        max_length=20,
    )


class GroupRerankRequest(
    BaseModel
):
    group_id: str = Field(
        min_length=1,
        max_length=128,
    )

    profile_ids: list[
        str
    ] = Field(
        min_length=2,
        max_length=20,
    )

    candidates: list[
        CurrentJourneyInput
    ] = Field(
        min_length=1,
        max_length=100,
    )


# ============================================================
# Cold Start
# ============================================================


@router.get(
    "/cold-start/questions",
    response_model=(
        ColdStartQuestionsResponse
    ),
)
async def cold_start_questions(
    limit: int = Query(
        default=6,
        ge=1,
        le=6,
    ),
) -> ColdStartQuestionsResponse:
    questions = (
        get_cold_start_questions(
            limit=limit
        )
    )

    return (
        ColdStartQuestionsResponse(
            total=len(
                questions
            ),
            minimum_choices=min(
                4,
                len(questions),
            ),
            questions=questions,
        )
    )


@router.post(
    "/cold-start/complete",
    response_model=ColdStartCompletion,
)
async def complete_cold_start(
    request: ColdStartCompleteRequest,
) -> ColdStartCompletion:
    try:
        service = (
            ColdStartService()
        )

        return service.complete(
            profile_id=(
                request.profile_id
            ),
            choices=request.choices,
            replace=request.replace,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# ============================================================
# Group Preferences
# ============================================================


@router.post(
    "/group/profile",
    response_model=(
        GroupPreferenceSummary
    ),
)
async def group_profile(
    request: GroupProfileRequest,
) -> GroupPreferenceSummary:
    try:
        service = (
            get_group_preference_service()
        )

        return service.build_profile(
            group_id=(
                request.group_id
            ),
            profile_ids=(
                request.profile_ids
            ),
        )

    except (
        MissingGroupProfilesError
    ) as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "message": (
                    "One or more preference "
                    "profiles were not found"
                ),
                "missing_profile_ids": (
                    exc.profile_ids
                ),
            },
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post(
    "/group/rerank",
    response_model=(
        GroupRerankResult
    ),
)
async def group_rerank(
    request: GroupRerankRequest,
) -> GroupRerankResult:
    try:
        journeys = [
            to_domain_journey(
                candidate
            )
            for candidate
            in request.candidates
        ]

        service = (
            get_group_preference_service()
        )

        return service.rerank(
            group_id=(
                request.group_id
            ),
            profile_ids=(
                request.profile_ids
            ),
            journeys=journeys,
        )

    except (
        MissingGroupProfilesError
    ) as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "message": (
                    "One or more preference "
                    "profiles were not found"
                ),
                "missing_profile_ids": (
                    exc.profile_ids
                ),
            },
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# ============================================================
# Behavioural preference learning
# ============================================================


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


# ============================================================
# Individual rerank
# ============================================================


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


# ============================================================
# Individual profile
#
# Dynamic routes stay LAST.
# ============================================================


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