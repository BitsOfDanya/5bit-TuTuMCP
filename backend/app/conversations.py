import asyncio
from functools import lru_cache
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationRecord, MessageRecord, utc_now
from app.schemas import TripDetails


class ConversationAccessError(Exception):
    """Raised when a conversation belongs to another user."""


class SessionLockRegistry:
    """Serialize turns for the same session within one API process."""

    def __init__(self) -> None:
        self._session_locks: dict[UUID, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    async def session_lock(self, session_id: UUID) -> asyncio.Lock:
        async with self._registry_lock:
            return self._session_locks.setdefault(session_id, asyncio.Lock())


@lru_cache
def get_session_lock_registry() -> SessionLockRegistry:
    return SessionLockRegistry()


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_or_create(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> tuple[ConversationRecord, list[MessageRecord]]:
        conversation = await self._session.get(ConversationRecord, session_id)
        if conversation is not None and conversation.user_id != user_id:
            await self._session.rollback()
            raise ConversationAccessError

        if conversation is None:
            conversation = ConversationRecord(
                id=session_id,
                user_id=user_id,
                trip=TripDetails().model_dump(mode="json"),
            )
            self._session.add(conversation)
            await self._session.flush()

        messages = await self._list_messages(session_id)
        await self._session.commit()
        return conversation, messages

    async def load(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> tuple[ConversationRecord, list[MessageRecord]] | None:
        conversation = await self._session.get(ConversationRecord, session_id)
        if conversation is None or conversation.user_id != user_id:
            await self._session.rollback()
            return None

        messages = await self._list_messages(session_id)
        await self._session.commit()
        return conversation, messages

    async def save_turn(
        self,
        conversation: ConversationRecord,
        trip: TripDetails,
        user_message: str,
        assistant_message: str,
    ) -> None:
        now = utc_now()
        conversation.trip = trip.model_dump(mode="json")
        conversation.updated_at = now
        self._session.add_all(
            [
                MessageRecord(
                    conversation_id=conversation.id,
                    role="user",
                    content=user_message,
                    created_at=now,
                ),
                MessageRecord(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=assistant_message,
                    created_at=now,
                ),
            ]
        )
        await self._session.commit()

    async def list_for_user(
        self,
        user_id: UUID,
    ) -> list[tuple[ConversationRecord, int]]:
        statement = (
            select(ConversationRecord, func.count(MessageRecord.id))
            .outerjoin(MessageRecord, MessageRecord.conversation_id == ConversationRecord.id)
            .where(ConversationRecord.user_id == user_id)
            .group_by(ConversationRecord.id)
            .order_by(ConversationRecord.updated_at.desc())
        )
        result = await self._session.execute(statement)
        rows = [(conversation, count) for conversation, count in result.all()]
        await self._session.commit()
        return rows

    async def _list_messages(self, session_id: UUID) -> list[MessageRecord]:
        statement = (
            select(MessageRecord)
            .where(MessageRecord.conversation_id == session_id)
            .order_by(MessageRecord.id)
        )
        return list(await self._session.scalars(statement))
