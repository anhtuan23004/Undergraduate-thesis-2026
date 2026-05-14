"""MongoDB client utility with singleton pattern."""

import structlog
from config import settings
from persistence.mongodb_config import get_mongodb_client_kwargs, normalize_mongodb_url
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

logger = structlog.get_logger()

_client: MongoClient | None = None
_db: Database | None = None


def get_mongodb_client() -> MongoClient:
    """Get or create MongoDB client singleton."""
    global _client
    if _client is None:
        client_kwargs = get_mongodb_client_kwargs()
        logger.info(
            "Creating MongoDB client",
            db=settings.MONGODB_DB,
            max_pool_size=client_kwargs["maxPoolSize"],
            min_pool_size=client_kwargs["minPoolSize"],
        )
        _client = MongoClient(
            normalize_mongodb_url(settings.MONGODB_URL),
            **client_kwargs,
        )
    return _client


def get_database() -> Database:
    """Get the MongoDB database instance."""
    global _db
    if _db is None:
        client = get_mongodb_client()
        _db = client[settings.MONGODB_DB]
    return _db


def get_collection(name: str) -> Collection:
    """Get a MongoDB collection by name."""
    return get_database()[name]


def get_medicine_collection() -> Collection:
    """Get the medicine collection from configured document_qa database."""
    client = get_mongodb_client()
    return client[settings.MEDICINE_DB]["medicine"]


def close_mongodb_client() -> None:
    """Close MongoDB client connection."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
    _db = None
