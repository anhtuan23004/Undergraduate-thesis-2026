from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Attributes:
        GEMINI_API_KEY (str): API key for Gemini.
        GEMINI_MODEL (str): Model name to use (default: gemini-2.5-pro).
        PROJECT_NAME (str): Application name.
        VERSION (str): Application version.
        API_PREFIX (str): API route prefix.
        LOG_LEVEL (str): Logging level.
        LOG_FILE (str): Log file path.
        GEMINI_MODEL (str): Model name to use.
        GEMINI_TEMPERATURE (Optional[float]): Temperature for Gemini.
        GEMINI_TOP_P (Optional[float]): Top-p for Gemini.
        GEMINI_TOP_K (Optional[int]): Top-k for Gemini.
        GEMINI_MAX_OUTPUT_TOKENS (Optional[int]): Max output tokens for Gemini.
        GEMINI_THINKING_BUDGET (Optional[int]): Thinking budget for Gemini 2.5 Series.
        GEMINI_THINKING_LEVEL (Optional[str]): Thinking level for Gemini 3 Series.
    """
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-pro"
    
    # Generation Config
    GEMINI_TEMPERATURE: Optional[float] = None
    GEMINI_TOP_P: Optional[float] = None
    GEMINI_TOP_K: Optional[int] = None
    GEMINI_MAX_OUTPUT_TOKENS: Optional[int] = None
    
    # Thinking Config (version-specific)
    GEMINI_THINKING_BUDGET: Optional[int] = None  # For Gemini 2.5: None=use default, -1=dynamic, 0=disabled, >0=token budget
    GEMINI_THINKING_LEVEL: Optional[str] = None  # For Gemini 3: None=use default (high), or minimal/low/medium/high  
    
    # App Info
    PROJECT_NAME: str = "Gemini OCR API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "ocr_service.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
