"""Configuration for agent service."""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    APP_NAME: str = "Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"  # nosec: B104 - localhost binding for development
    PORT: int = 8003

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 8192

    MONGODB_URL: str = (
        "mongodb://admin:admin123@localhost:27017/claims?authSource=admin&directConnection=true"
    )
    MONGODB_URL_AGENT: str = (
        "mongodb://admin:admin123@localhost:27017/agent?authSource=admin&directConnection=true"
    )
    MONGODB_DB: str = "claims"
    MEDICINE_DB: str = "document_qa"
    OCR_SERVICE_URL: str = "http://localhost:8091"

    PROCESS_TIMEOUT: int = 300
    OCR_TIMEOUT: int = 120
    UPLOADS_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 20
    PAUSE_AT_EACH_STAGE: bool = False

    AGENT_REVIEW_AMOUNT_THRESHOLD: int = 5_000_000
    AGENT_REVIEW_CONFIDENCE_THRESHOLD: float = 0.9

    ALLOWED_ORIGINS: str = ""

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_ENABLED: bool = False

    TAVILY_API_KEY: str = ""

    @field_validator("DEBUG", "LANGFUSE_ENABLED", "PAUSE_AT_EACH_STAGE", mode="before")
    @classmethod
    def parse_bool_like_env(cls, value: Any) -> Any:
        """Accept common deployment mode strings for boolean env values."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
