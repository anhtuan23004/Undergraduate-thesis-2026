"""Logging utilities for the OCR service."""

import logging
import sys
from typing import Final

from app.config import settings

LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging() -> None:
    """Configure logging for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handlers = [
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=log_level, format=LOG_FORMAT, handlers=handlers)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)
