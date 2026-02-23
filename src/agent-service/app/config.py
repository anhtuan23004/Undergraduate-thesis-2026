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

    # LLM
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.3
    OPENAI_MAX_TOKENS: int = 2000

    # RAG Service
    RAG_SERVICE_URL: str = "http://rag-service:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

