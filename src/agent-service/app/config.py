"""Configuration for agent service."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # App
    APP_NAME: str = "Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "claims"

    # LLM
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_TEMPERATURE: float = 0.3
    OPENAI_MAX_TOKENS: int = 2000

    # Langfuse
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "http://localhost:3000"

    # RAG Service
    RAG_SERVICE_URL: str = "http://rag-service:8000"

    # Agent
    MAX_ITERATIONS: int = 10
    CONFIDENCE_THRESHOLD: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
