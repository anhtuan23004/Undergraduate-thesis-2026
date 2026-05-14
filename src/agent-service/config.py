"""Configuration for agent service."""

from typing import Any

from pydantic import field_validator, model_validator
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
    MONGODB_DB: str = "claims"
    MONGODB_CONNECT_TIMEOUT_MS: int = 5000
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    MONGODB_SOCKET_TIMEOUT_MS: int = 20000
    MONGODB_MAX_POOL_SIZE: int = 20
    MONGODB_MIN_POOL_SIZE: int = 0

    MEDICINE_DB: str = "document_qa"
    OCR_SERVICE_URL: str = "http://localhost:8091"
    OCR_API_VERSION: str = "v2"
    OCR_V2_PIPELINE: str = "two_phase_gated"
    OCR_V2_EXTRACT_ALL_FIELDS: bool = False
    OCR_V2_DOCUMENT_CODES: str = ""
    OCR_V2_MODEL: str = ""

    PROCESS_TIMEOUT: int = 300
    OCR_TIMEOUT: int = 120
    OUTBOUND_HTTP_CONNECT_TIMEOUT: int = 10
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

    @field_validator(
        "DEBUG",
        "LANGFUSE_ENABLED",
        "PAUSE_AT_EACH_STAGE",
        "OCR_V2_EXTRACT_ALL_FIELDS",
        mode="before",
    )
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

    @field_validator("OCR_API_VERSION", mode="before")
    @classmethod
    def normalize_ocr_api_version(cls, value: Any) -> Any:
        """Normalize and validate supported OCR API versions."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized not in {"v1", "v2"}:
                raise ValueError("OCR_API_VERSION must be either 'v1' or 'v2'")
            return normalized
        return value

    @model_validator(mode="after")
    def validate_ocr_pipeline(self):
        """Keep OCR v2 cache keys aligned with the only implemented pipeline."""
        if self.OCR_API_VERSION == "v2" and self.OCR_V2_PIPELINE != "two_phase_gated":
            raise ValueError("OCR_V2_PIPELINE must be 'two_phase_gated'")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def comma_separated_values(value: str) -> list[str]:
    """Parse comma-separated env settings into non-empty values."""
    return [item.strip() for item in value.split(",") if item.strip()]


def get_cors_origins(config: Settings | None = None) -> list[str]:
    """Return allowed CORS origins, avoiding wildcard defaults outside debug."""
    config = config or settings
    configured_origins = comma_separated_values(config.ALLOWED_ORIGINS)
    if configured_origins:
        return configured_origins
    if config.DEBUG:
        return ["*"]
    return []


def validate_startup_config(config: Settings | None = None) -> None:
    """Validate settings that must be present when the FastAPI app starts."""
    config = config or settings
    missing = [
        name
        for name in ("GEMINI_API_KEY", "MONGODB_URL", "OCR_SERVICE_URL")
        if not str(getattr(config, name, "")).strip()
    ]
    if not config.DEBUG and missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing required environment values: {names}")

    if not config.DEBUG and "*" in get_cors_origins(config):
        raise RuntimeError("ALLOWED_ORIGINS cannot include '*' when DEBUG is false")
