"""Configuration for agent service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App
    APP_NAME: str = "Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Gemini
    GEMINI_API_KEY: str = ""  # Can be empty for local testing, but needed for production
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_TEMPERATURE: float = 0.3  # Standard for agent tasks
    GEMINI_MAX_TOKENS: int = 8192

    # RAG Service
    RAG_SERVICE_URL: str = "http://rag-service:8000"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "claims"

    # Langfuse
    LANGFUSE_HOST: str = "http://localhost:3000"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL_SECONDS: int = 86400  # 24 hours for claim data

    # Agent Configuration
    MAX_ITERATIONS: int = 10
    CONFIDENCE_THRESHOLD: float = 0.7

    # Business Logic Thresholds
    CLAIM_AMOUNT_THRESHOLD: float = 1_000_000_000  # 1 billion VND
    CLAIM_AMOUNT_TOLERANCE: float = 0.01  # For floating point comparison

    # Decision Agent Thresholds (used for issue severity scoring)
    CRITICAL_THRESHOLD: int = 1   # Any critical issue triggers rejection
    HIGH_THRESHOLD: int = 3        # 3+ high severity issues trigger rejection
    MEDIUM_THRESHOLD: int = 5     # 5+ medium severity issues trigger review
    SCORE_THRESHOLD: int = 8       # Weighted score threshold for rejection

    # Prior Authorization Medications (comma-separated list)
    PRIOR_AUTH_MEDICATIONS: str = "morphine,warfarin,biologics,specialty_drugs"

    # CORS Configuration
    ALLOWED_ORIGINS: str = ""  # Comma-separated list of allowed origins (empty = allow all)

    # External Data Sources (file paths for mock data - replace with real DB in production)
    ICD10_DATA_PATH: str = ""  # Path to ICD-10 JSON file (optional)
    POLICY_EXCLUSIONS_PATH: str = ""  # Path to policy exclusions JSON file (optional)

    @property
    def prior_auth_medications_list(self) -> list[str]:
        """Return prior auth medications as a list."""
        return [med.strip().lower() for med in self.PRIOR_AUTH_MEDICATIONS.split(",") if med.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

