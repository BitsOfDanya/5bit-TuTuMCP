from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations import ConversationRepository
from app.models import Base
from app.schemas import TravelService, TripDetails


@pytest.mark.asyncio
async def test_history_persists_after_database_reconnect(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'history.db'}"
    user_id = uuid4()
    conversation_id = uuid4()
    trip = TripDetails(
        service_type=TravelService.BUS,
        origin="Москва",
        destination="Тула",
    )

    first_engine = create_async_engine(database_url)
    async with first_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    first_session_factory = async_sessionmaker(first_engine, expire_on_commit=False)
    async with first_session_factory() as session:
        repository = ConversationRepository(session)
        conversation, _ = await repository.load_or_create(user_id, conversation_id)
        await repository.save_turn(
            conversation,
            trip,
            "Нужен автобус из Москвы в Тулу",
            "Когда хотите поехать?",
        )
    await first_engine.dispose()

    second_engine = create_async_engine(database_url)
    second_session_factory = async_sessionmaker(second_engine, expire_on_commit=False)
    async with second_session_factory() as session:
        stored = await ConversationRepository(session).load(user_id, conversation_id)

    await second_engine.dispose()

    assert stored is not None
    conversation, messages = stored
    assert conversation.trip["service_type"] == "bus"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "Нужен автобус из Москвы в Тулу"
