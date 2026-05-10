"""Application configuration module."""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    GEMINI_API_KEY: str

    # Model Configuration
    GEMINI_MODEL: str = "gemini-2.5-pro"
    GEMINI_TEMPERATURE: float | None = None
    GEMINI_TOP_P: float | None = None
    GEMINI_TOP_K: int | None = None
    GEMINI_MAX_OUTPUT_TOKENS: int | None = None

    # Thinking Configuration (version-specific)
    # Gemini 2.5: -1=dynamic, 0=disabled, >0=token budget
    GEMINI_THINKING_BUDGET: int | None = None
    # Gemini 3: minimal/low/medium/high
    GEMINI_THINKING_LEVEL: str | None = None

    # V2 Pipeline Configuration
    GEMINI_MAX_INLINE_IN_BYTES: int = 104857600  # 100MB threshold for inline vs Files API
    GEMINI_MAX_CONCURRENT_EXTRACTIONS: int = 3  # Max concurrent extractions in 2-stage pipeline
    OCR_EXTRACT_ALL_DOCUMENTS: bool = True  # Allow unknown documents in v2 classify/extract
    OCR_HIGH_ACCURACY_DOCUMENT_CODES: str = "claim_form"
    OCR_HIGH_ACCURACY_MODEL: str = "gemini-2.5-pro"

    # Application Info
    PROJECT_NAME: str = "Gemini OCR API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    API_V2_PREFIX: str = "/api/v2"
    API_V3_PREFIX: str = "/api/v3"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "ocr_service.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
