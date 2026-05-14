"""MongoDB connection configuration helpers."""

from __future__ import annotations

from config import settings


def normalize_mongodb_url(mongo_url: str) -> str:
    """Ensure MongoDB URL uses direct connection for local checkpointing."""
    if "directConnection" in mongo_url:
        return mongo_url
    separator = "&" if "?" in mongo_url else "?"
    return f"{mongo_url}{separator}directConnection=true"


def get_mongodb_client_kwargs() -> dict[str, int]:
    """Return explicit PyMongo timeout options from settings."""
    return {
        "connectTimeoutMS": settings.MONGODB_CONNECT_TIMEOUT_MS,
        "serverSelectionTimeoutMS": settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        "socketTimeoutMS": settings.MONGODB_SOCKET_TIMEOUT_MS,
    }
