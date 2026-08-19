import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.config import get_database_settings


def test_alembic_migration_builds_current_schema(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_database_settings.cache_clear()

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    get_database_settings.cache_clear()

    assert {"alembic_version", "conversations", "messages"} <= tables
    assert revision == ("20260819_0001",)

    command.downgrade(config, "base")
    with sqlite3.connect(database_path) as connection:
        tables_after_downgrade = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert "conversations" not in tables_after_downgrade
    assert "messages" not in tables_after_downgrade

    command.upgrade(config, "head")
    get_database_settings.cache_clear()
