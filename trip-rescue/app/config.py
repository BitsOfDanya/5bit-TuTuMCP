from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]
ROOT_ENV_FILE = SERVICE_DIR.parent / ".env"
LEGACY_BACKEND_ENV_FILE = SERVICE_DIR.parent / "backend" / ".env"
SERVICE_ENV_FILE = SERVICE_DIR / ".env"


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8010
    app_debug: bool = True

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-luna"

    agent_system_prompt: str = (
        "You are a helpful assistant. "
        "Be concise and accurate."
    )

    tutu_mcp_url: str = "https://mcp.tutu.ru/mcp"

    cors_origins: str = (
        "http://localhost:5173,"
        "http://localhost:3000"
    )

    model_config = SettingsConfigDict(
        env_file=(ROOT_ENV_FILE, LEGACY_BACKEND_ENV_FILE, SERVICE_ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
