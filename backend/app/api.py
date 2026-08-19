import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_client import AIServiceClientDep, AIServiceError
from app.auth_dependencies import OptionalCurrentUserDep
from app.config import get_database_settings
from app.conversations import (
    ConversationAccessError,
    ConversationRepository,
    SessionLockRegistry,
    get_session_lock_registry,
)
from app.database import get_db_session
from app.document_uploads import (
    DocumentMediaType,
    validate_document_upload,
)
from app.schemas import (
    AgentRequest,
    AgentResponse,
    ChatMessage,
    ConversationHistoryResponse,
    ConversationSummary,
    PassengerDocumentExtractionResponse,
    SearchOption,
    TravelService,
    TripDetails,
    UserConversationsResponse,
    missing_trip_fields,
)
from app.travel_rules import next_travel_action, search_redirect_url
from app.trip_rescue_client import TripRescueClientDep, TripRescueError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
DatabaseSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SessionLocksDep = Annotated[SessionLockRegistry, Depends(get_session_lock_registry)]
DocumentUpload = Annotated[UploadFile, File(description="One PNG, JPEG, or PDF document.")]


@router.post("/chat")
async def chat_with_agent(
    request: AgentRequest,
    ai_client: AIServiceClientDep,
    database_session: DatabaseSessionDep,
    session_locks: SessionLocksDep,
    current_user: OptionalCurrentUserDep,
    trip_rescue: TripRescueClientDep,
) -> AgentResponse:
    session_id = request.session_id or uuid4()
    lock = await session_locks.session_lock(session_id)
    repository = ConversationRepository(database_session)

    async with lock:
        try:
            conversation, stored_messages = await repository.load_or_create(
                request.user_id,
                session_id,
            )
        except ConversationAccessError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            ) from exc

        current_trip = TripDetails.model_validate(conversation.trip)
        messages = [
            *[{"role": message.role, "content": message.content} for message in stored_messages],
            {"role": "user", "content": request.message},
        ]

        try:
            result = await ai_client.chat(
                messages=messages,
                current_trip=current_trip,
            )
        except AIServiceError as exc:
            logger.exception("AI service invocation failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        trip = result.trip
        search_options = result.search_options
        if current_user is not None and current_user.id == str(request.user_id):
            search_options = await _personalize_search_options(
                search_options,
                profile_id=current_user.id,
                trip_rescue=trip_rescue,
            )
        await repository.save_turn(
            conversation,
            trip,
            request.message,
            result.response,
        )

        return AgentResponse(
            user_id=request.user_id,
            session_id=session_id,
            response=result.response,
            trip=trip,
            missing_fields=result.missing_fields,
            is_complete=result.is_complete,
            next_action=result.next_action,
            plan=result.plan,
            tools_used=result.tools_used,
            tool_statuses=result.tool_statuses,
            search_options=search_options,
            redirect_url=result.redirect_url,
            decision_intent=result.decision_intent,
        )


async def _personalize_search_options(
    search_options: list[SearchOption],
    *,
    profile_id: str,
    trip_rescue: object,
) -> list[SearchOption]:
    eligible = [
        option
        for option in search_options
        if option.outbound is not None and option.inbound is not None
    ]
    if len(eligible) < 2:
        return search_options

    candidates = [
        {
            "id": option.id,
            "total_price": option.total_price,
            "outbound": option.outbound.model_dump(mode="json"),
            "inbound": option.inbound.model_dump(mode="json"),
            "hotel": option.hotel.model_dump(mode="json") if option.hotel else None,
        }
        for option in eligible
    ]
    try:
        payload = await trip_rescue.rerank_preferences(
            profile_id=profile_id,
            candidates=candidates,
        )
    except TripRescueError:
        logger.warning("Preference reranking failed; returning original search order")
        return search_options

    ranked_items = payload.get("items", [])
    if not isinstance(ranked_items, list):
        return search_options
    metadata = {
        item.get("candidate_id"): item
        for item in ranked_items
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    }
    decorated: list[SearchOption] = []
    for option in search_options:
        item = metadata.get(option.id)
        if item is None:
            decorated.append(option)
            continue
        decorated.append(option.model_copy(update={
            "personalized": True,
            "preference_score": item.get("preference_score"),
            "preference_reasons": item.get("reasons", []),
            "rank_before": item.get("rank_before"),
            "rank_after": item.get("rank_after"),
        }))
    return sorted(
        decorated,
        key=lambda option: option.rank_after if option.rank_after is not None else 10_000,
    )


@router.get("/users/{user_id}/sessions/{session_id}")
async def get_conversation_history(
    user_id: UUID,
    session_id: UUID,
    database_session: DatabaseSessionDep,
    session_locks: SessionLocksDep,
) -> ConversationHistoryResponse:
    lock = await session_locks.session_lock(session_id)
    repository = ConversationRepository(database_session)

    async with lock:
        stored = await repository.load(user_id, session_id)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        conversation, stored_messages = stored

    trip = TripDetails.model_validate(conversation.trip)
    messages = [
        ChatMessage(
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )
        for message in stored_messages
    ]
    missing_fields = missing_trip_fields(trip)
    next_action = next_travel_action(trip)
    redirect_url = search_redirect_url(trip) if next_action.value == "redirect_to_search" else None

    return ConversationHistoryResponse(
        user_id=user_id,
        session_id=session_id,
        messages=messages,
        trip=trip,
        missing_fields=missing_fields,
        is_complete=not missing_fields,
        next_action=next_action,
        redirect_url=redirect_url,
    )


@router.get("/users/{user_id}/sessions")
async def list_user_conversations(
    user_id: UUID,
    database_session: DatabaseSessionDep,
) -> UserConversationsResponse:
    repository = ConversationRepository(database_session)
    conversations = await repository.list_for_user(user_id)

    return UserConversationsResponse(
        user_id=user_id,
        sessions=[
            ConversationSummary(
                session_id=conversation.id,
                trip=TripDetails.model_validate(conversation.trip),
                message_count=message_count,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            for conversation, message_count in conversations
        ],
    )


@router.post("/users/{user_id}/sessions/{session_id}/documents/extract")
async def extract_passenger_document(
    user_id: UUID,
    session_id: UUID,
    document: DocumentUpload,
    ai_client: AIServiceClientDep,
    database_session: DatabaseSessionDep,
    session_locks: SessionLocksDep,
) -> PassengerDocumentExtractionResponse:
    lock = await session_locks.session_lock(session_id)
    repository = ConversationRepository(database_session)

    async with lock:
        stored = await repository.load(user_id, session_id)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        conversation, _ = stored
        trip = TripDetails.model_validate(conversation.trip)

    if trip.service_type is not TravelService.FLIGHT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document extraction is available only for a flight session.",
        )

    max_size = get_database_settings().max_document_size_bytes
    content = await document.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The document exceeds the {max_size // (1024 * 1024)} MB limit.",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded document is empty.",
        )

    try:
        media_type: DocumentMediaType = validate_document_upload(
            filename=document.filename,
            declared_media_type=document.content_type,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    try:
        extracted = await ai_client.extract_document(
            filename=f"document{_extension_for(media_type)}",
            media_type=media_type,
            content=content,
        )
    except AIServiceError as exc:
        logger.exception("AI document extraction failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return PassengerDocumentExtractionResponse(
        user_id=user_id,
        session_id=session_id,
        media_type=extracted.media_type,
        document=extracted.document,
        missing_fields=extracted.missing_fields,
        manual_review_required=extracted.manual_review_required,
    )


def _extension_for(media_type: DocumentMediaType) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "application/pdf": ".pdf",
    }[media_type]
