from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import get_database_settings
from app.models import Base


@lru_cache
def get_engine() -> AsyncEngine:
    database_url = get_database_settings().database_url
    engine_options: dict[str, object] = {}
    if database_url.endswith(":memory:"):
        engine_options["poolclass"] = StaticPool

    engine = create_async_engine(database_url, **engine_options)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


async def initialize_database() -> None:
    """Create tables directly for isolated tests; production uses Alembic."""
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
