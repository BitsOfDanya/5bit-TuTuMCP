from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / ".data" / "tutumcp.db"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DATABASE_PATH}"
    max_document_size_bytes: int = 10 * 1024 * 1024


class Settings(DatabaseSettings):
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5.6-luna"
    document_extraction_model: str = "gpt-5.6-luna"
    agent_system_prompt: str = "You are a helpful assistant. Be concise and accurate."
    auth_secret_key: SecretStr = SecretStr("local-development-key-change-me-please")
    auth_cookie_name: str = "tutumcp_session"
    auth_debug: bool = True
    auth_code_ttl_seconds: int = 300
    auth_session_ttl_seconds: int = 60 * 60 * 24 * 7


def ensure_sqlite_parent(database_url: str) -> None:
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if database_url.startswith(prefix):
            database_path = database_url.removeprefix(prefix)
            if database_path != ":memory:" and not database_path.startswith("file:"):
                Path(database_path).expanduser().resolve().parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
            return


@lru_cache
def get_database_settings() -> DatabaseSettings:
    settings = DatabaseSettings()
    ensure_sqlite_parent(settings.database_url)
    return settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
