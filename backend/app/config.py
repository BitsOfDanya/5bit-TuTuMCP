from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]
ROOT_ENV_FILE = SERVICE_DIR.parent / ".env"
ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / ".data" / "tutumcp.db"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_ENV_FILE, ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DATABASE_PATH}"
    max_document_size_bytes: int = 10 * 1024 * 1024


class Settings(DatabaseSettings):
    ai_service_url: str = "http://127.0.0.1:8020"
    ai_service_token: SecretStr = SecretStr("")
    ai_service_timeout_seconds: float = 90.0
    smart_trip_tracker_url: str = "http://127.0.0.1:8001"
    smart_trip_tracker_timeout_seconds: float = 60.0
    trip_rescue_url: str = "http://127.0.0.1:8030"
    trip_rescue_timeout_seconds: float = 120.0
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
