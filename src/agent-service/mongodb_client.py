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


def get_recent_claims(policy_number: str, days: int = 30) -> list[dict]:
    """Get recent claims for a policy number within a specified number of days."""
    from datetime import UTC, datetime, timedelta

    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    claims_col = get_collection("claims")
    cursor = claims_col.find(
        {
            "policy_number": policy_number,
            "created_at": {"$gte": cutoff_date},
            "status": {"$in": ["approved", "auto_approved"]},
        }
    ).sort("created_at", -1)

    return list(cursor)


def get_recent_claims_total(policy_number: str, days: int = 30) -> float:
    """Calculate the total approved amount for a policy within recent days."""
    claims = get_recent_claims(policy_number, days)
    total = 0.0
    for claim in claims:
        amount = claim.get("amount", 0)
        if isinstance(amount, int | float):
            total += amount
        elif isinstance(amount, str):
            try:
                total += float(amount.replace(",", "").replace(".", ""))
            except ValueError:
                pass
    return total


def close_mongodb_client() -> None:
    """Close MongoDB client connection."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
    _db = None
