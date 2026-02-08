"""Langfuse client for observability and tracing."""
import logging
from typing import Optional

from langfuse import Langfuse
from app.config import settings

logger = logging.getLogger(__name__)

# Global Langfuse instance
_langfuse_instance: Optional[Langfuse] = None


def get_langfuse() -> Optional[Langfuse]:
    """Get or initialize Langfuse client.

    Returns None if Langfuse is not configured (LANGFUSE_PUBLIC_KEY not set).
    This allows the application to run without Langfuse.

    Returns:
        Langfuse client instance or None if not configured.
    """
    global _langfuse_instance

    # Already initialized
    if _langfuse_instance is not None:
        return _langfuse_instance

    # Check if Langfuse is configured
    if not settings.LANGFUSE_PUBLIC_KEY:
        logger.debug("Langfuse not configured - tracing disabled")
        return None

    try:
        _langfuse_instance = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info(
            "Langfuse initialized",
            extra={"host": settings.LANGFUSE_HOST}
        )
        return _langfuse_instance
    except Exception as e:
        logger.warning(
            f"Failed to initialize Langfuse: {e}. Tracing disabled.",
            exc_info=True
        )
        return None


def is_langfuse_enabled() -> bool:
    """Check if Langfuse tracing is enabled.

    Returns:
        True if Langfuse is configured and initialized.
    """
    return get_langfuse() is not None


# Export singleton-like access
langfuse = get_langfuse()
