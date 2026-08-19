from fastapi import APIRouter, HTTPException, Query

from app.auth_dependencies import CurrentUserDep
from app.schemas import (
    ColdStartCompleteRequest,
    ColdStartCompletionResponse,
    ColdStartQuestionsResponse,
    GroupPreferenceRequest,
    GroupPreferenceResponse,
    GroupRerankFacadeRequest,
    PreferenceProfileEnvelope,
)
from app.trip_rescue_client import TripRescueClientDep, TripRescueError

router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])


@router.get("/cold-start/questions", response_model=ColdStartQuestionsResponse)
async def cold_start_questions(
    user: CurrentUserDep,
    trip_rescue: TripRescueClientDep,
    limit: int = Query(default=4, ge=4, le=6),
) -> ColdStartQuestionsResponse:
    del user
    try:
        payload = await trip_rescue.get_cold_start_questions(limit=limit)
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return ColdStartQuestionsResponse.model_validate(payload)


@router.post("/cold-start/complete", response_model=ColdStartCompletionResponse)
async def complete_cold_start(
    request: ColdStartCompleteRequest,
    user: CurrentUserDep,
    trip_rescue: TripRescueClientDep,
) -> ColdStartCompletionResponse:
    try:
        payload = await trip_rescue.complete_cold_start(
            profile_id=user.id,
            choices=[choice.model_dump() for choice in request.choices],
            replace=request.replace,
        )
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return ColdStartCompletionResponse.model_validate(payload)


@router.get("/me", response_model=PreferenceProfileEnvelope)
async def get_my_preference_profile(
    user: CurrentUserDep,
    trip_rescue: TripRescueClientDep,
) -> PreferenceProfileEnvelope:
    try:
        profile = await trip_rescue.get_profile(user.id)
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return PreferenceProfileEnvelope(profile=profile)


@router.post("/group/profile", response_model=GroupPreferenceResponse)
async def build_group_profile(
    request: GroupPreferenceRequest,
    user: CurrentUserDep,
    trip_rescue: TripRescueClientDep,
) -> GroupPreferenceResponse:
    profile_ids = _group_profile_ids(user.id, request.participant_profile_ids)
    try:
        result = await trip_rescue.build_group_profile(
            group_id=request.group_id,
            profile_ids=profile_ids,
        )
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return GroupPreferenceResponse(result=result)


@router.post("/group/rerank", response_model=GroupPreferenceResponse)
async def rerank_group(
    request: GroupRerankFacadeRequest,
    user: CurrentUserDep,
    trip_rescue: TripRescueClientDep,
) -> GroupPreferenceResponse:
    profile_ids = _group_profile_ids(user.id, request.participant_profile_ids)
    try:
        result = await trip_rescue.rerank_group(
            group_id=request.group_id,
            profile_ids=profile_ids,
            candidates=[candidate.model_dump(mode="json") for candidate in request.candidates],
        )
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return GroupPreferenceResponse(result=result)


def _group_profile_ids(owner_profile_id: str, participant_ids: list[str]) -> list[str]:
    profile_ids = list(
        dict.fromkeys(
            [owner_profile_id, *(profile_id.strip() for profile_id in participant_ids)]
        )
    )
    profile_ids = [profile_id for profile_id in profile_ids if profile_id]
    if len(profile_ids) < 2:
        raise HTTPException(status_code=422, detail="Добавьте хотя бы одного участника.")
    return profile_ids


def _http_error(exc: TripRescueError) -> HTTPException:
    upstream_status = exc.status_code
    status_code = upstream_status if 400 <= upstream_status < 500 else 502
    return HTTPException(status_code=status_code, detail=exc.detail)
