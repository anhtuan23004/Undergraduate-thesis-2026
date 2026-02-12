"""Configuration for RAG service."""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App
    APP_NAME: str = "RAG Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "insurance_kb_v2"
    MILVUS_DIM: int = 3072  # Gemini embedding dimension

    # MongoDB (for document metadata)
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "claims"

    # Gemini (for embeddings and OCR)
    GEMINI_API_KEY: str
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Optional OpenAI (for backward compatibility)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Search
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    TOP_K: int = 5
    RRF_K: int = 60  # Reciprocal Rank Fusion constant

    # Chunking
    PARENT_CHUNK_SIZE: int = 2048
    CHILD_CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
