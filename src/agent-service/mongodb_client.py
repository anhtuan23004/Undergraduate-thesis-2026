"""MongoDB client utility with singleton pattern."""

from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from config import settings

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def get_mongodb_client() -> MongoClient:
    """Get or create MongoDB client singleton."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URL)
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
    """Get the medicine collection."""
    return get_collection("medicine")


def close_mongodb_client():
    """Close MongoDB client connection."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
    _db = None
