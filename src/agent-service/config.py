"""Configuration for agent service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    APP_NAME: str = "Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8003

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 8192

    MONGODB_URL: str = "mongodb://localhost:27017"
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
