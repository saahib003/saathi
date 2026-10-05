"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Settings shared by the HTTP app and the database bootstrap."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_host: str = Field(default="127.0.0.1", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    app_session_token: str = Field(default="", validation_alias="APP_SESSION_TOKEN")
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        validation_alias="ALLOWED_ORIGINS",
    )
    database_url: str = Field(default="sqlite:///./laptop_agent.db", validation_alias="DATABASE_URL")
    log_retention_days: int = Field(default=30, validation_alias="LOG_RETENTION_DAYS")
    memory_enabled: bool = Field(default=True, validation_alias="MEMORY_ENABLED")
    default_terminal: str = Field(default="powershell", validation_alias="DEFAULT_TERMINAL")
    browser_enabled: bool = Field(default=False, validation_alias="BROWSER_ENABLED")
    computer_use_enabled: bool = Field(default=False, validation_alias="COMPUTER_USE_ENABLED")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="", validation_alias="GEMINI_MODEL")
    gemini_store_interactions: bool = Field(default=False, validation_alias="GEMINI_STORE_INTERACTIONS")
    gemini_timeout_seconds: float = Field(default=60, validation_alias="GEMINI_TIMEOUT_SECONDS")
    agent_max_retries: int = Field(default=2, validation_alias="AGENT_MAX_RETRIES")
    agent_max_steps: int = Field(default=20, validation_alias="AGENT_MAX_STEPS")
    confirmation_behavior: str = Field(default="ask", validation_alias="CONFIRMATION_BEHAVIOR")
    tool_timeout_seconds: float = Field(default=60, validation_alias="TOOL_TIMEOUT_SECONDS")
    tool_output_max_chars: int = Field(default=20_000, validation_alias="TOOL_OUTPUT_MAX_CHARS")
    allowed_roots: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [str(Path.cwd())],
        validation_alias="ALLOWED_ROOTS",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("allowed_roots", mode="before")
    @classmethod
    def parse_allowed_roots(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            roots = [root.strip() for root in value.split(",") if root.strip()]
            return roots or [str(Path.cwd())]
        return value

    def ensure_session_token(self) -> str:
        """Return the configured token, generating an in-memory fallback for local development."""
        if not self.app_session_token:
            self.app_session_token = token_urlsafe(32)
        return self.app_session_token

    def sqlite_path(self) -> Path:
        """Resolve the path from the supported local SQLite URL format."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Phase 1 supports only sqlite:/// database URLs")
        return Path(self.database_url.removeprefix(prefix)).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
