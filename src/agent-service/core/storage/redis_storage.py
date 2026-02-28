"""Redis storage utility for persisting claim processing state.

This module provides Redis-backed storage for thread errors and pending reviews,
replacing in-memory dicts that would be lost on service restart.
Uses async Redis client for non-blocking I/O in async FastAPI context.
"""

import json
from typing import Any, Dict, Optional

import redis.asyncio as redis
import structlog

from config import settings

logger = structlog.get_logger()


class RedisStorage:
    """Async Redis-backed storage for claim processing state.

    Provides thread-safe storage for:
    - thread_errors: Error messages from failed graph executions
    - pending_reviews: Claims waiting for human review

    All values are stored as JSON strings with optional TTL for automatic expiration.
    """

    def __init__(self, url: Optional[str] = None, ttl_seconds: Optional[int] = None):
        """Initialize Redis storage.

        Args:
            url: Redis connection URL. Defaults to settings.REDIS_URL
            ttl_seconds: Default TTL for keys in seconds. Defaults to settings.REDIS_TTL_SECONDS
        """
        self._client: Optional[redis.Redis] = None
        self._url = url or settings.REDIS_URL
        self._ttl = ttl_seconds or settings.REDIS_TTL_SECONDS
        self._prefix = "agent-service"

    async def _get_client(self) -> redis.Redis:
        """Get or create the async Redis client lazily."""
        if self._client is None:
            self._client = redis.from_url(
                self._url,
                decode_responses=True  # Returns strings instead of bytes
            )
        return self._client

    @property
    def client(self) -> redis.Redis:
        """Get the underlying Redis client (for backward compatibility)."""
        # Note: This returns None if client not initialized yet
        # Use _get_client() for async initialization
        return self._client

    def _make_key(self, category: str, key: str) -> str:
        """Create a namespaced Redis key."""
        return f"{self._prefix}:{category}:{key}"

    # Thread Errors
    async def set_error(self, thread_id: str, error: str, ttl: Optional[int] = None) -> None:
        """Store an error message for a thread.

        Args:
            thread_id: The thread/claim identifier
            error: Error message to store
            ttl: Optional TTL override in seconds
        """
        client = await self._get_client()
        redis_key = self._make_key("errors", thread_id)
        await client.set(redis_key, error, ex=ttl or self._ttl)
        logger.debug("Stored error in Redis", thread_id=thread_id, ttl=ttl or self._ttl)

    async def get_error(self, thread_id: str) -> Optional[str]:
        """Retrieve an error message for a thread.

        Args:
            thread_id: The thread/claim identifier

        Returns:
            Error message or None if not found
        """
        client = await self._get_client()
        redis_key = self._make_key("errors", thread_id)
        return await client.get(redis_key)

    async def delete_error(self, thread_id: str) -> bool:
        """Delete an error for a thread.

        Args:
            thread_id: The thread/claim identifier

        Returns:
            True if key was deleted, False if it didn't exist
        """
        client = await self._get_client()
        redis_key = self._make_key("errors", thread_id)
        result = await client.delete(redis_key)
        return bool(result)

    # Pending Reviews
    async def set_pending_review(self, claim_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Store pending review data for a claim.

        Args:
            claim_id: The claim identifier
            data: Dictionary containing review data
            ttl: Optional TTL override in seconds
        """
        client = await self._get_client()
        redis_key = self._make_key("pending", claim_id)
        json_data = json.dumps(data)
        await client.set(redis_key, json_data, ex=ttl or self._ttl)
        logger.debug("Stored pending review in Redis", claim_id=claim_id, ttl=ttl or self._ttl)

    async def get_pending_review(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve pending review data for a claim.

        Args:
            claim_id: The claim identifier

        Returns:
            Dictionary containing review data or None if not found
        """
        client = await self._get_client()
        redis_key = self._make_key("pending", claim_id)
        json_data = await client.get(redis_key)
        if json_data:
            return json.loads(json_data)
        return None

    async def delete_pending_review(self, claim_id: str) -> bool:
        """Delete pending review for a claim.

        Args:
            claim_id: The claim identifier

        Returns:
            True if key was deleted, False if it didn't exist
        """
        client = await self._get_client()
        redis_key = self._make_key("pending", claim_id)
        result = await client.delete(redis_key)
        return bool(result)

    async def get_all_pending_reviews(self) -> Dict[str, Dict[str, Any]]:
        """Get all pending reviews.

        Returns:
            Dictionary mapping claim_id to review data
        """
        client = await self._get_client()
        pattern = self._make_key("pending", "*")
        results = {}
        async for key in client.scan_iter(match=pattern):
            claim_id = key.split(":")[-1]
            data = await self.get_pending_review(claim_id)
            if data:
                results[claim_id] = data
        return results

    # Claim-Thread Mapping (for claim resumption after service restart)
    async def set_claim_thread_mapping(self, claim_id: str, thread_id: str, ttl: Optional[int] = None) -> None:
        """Store mapping between claim_id and thread_id for state resumption.

        Args:
            claim_id: The claim identifier
            thread_id: The thread identifier for LangGraph state
            ttl: Optional TTL override in seconds
        """
        client = await self._get_client()
        redis_key = self._make_key("mapping", claim_id)
        await client.set(redis_key, thread_id, ex=ttl or self._ttl)
        logger.debug("Stored claim-thread mapping in Redis", claim_id=claim_id, thread_id=thread_id)

    async def get_thread_by_claim(self, claim_id: str) -> Optional[str]:
        """Retrieve thread_id by claim_id.

        Args:
            claim_id: The claim identifier

        Returns:
            Thread ID or None if not found
        """
        client = await self._get_client()
        redis_key = self._make_key("mapping", claim_id)
        return await client.get(redis_key)

    async def delete_claim_thread_mapping(self, claim_id: str) -> bool:
        """Delete claim-thread mapping.

        Args:
            claim_id: The claim identifier

        Returns:
            True if key was deleted, False if it didn't exist
        """
        client = await self._get_client()
        redis_key = self._make_key("mapping", claim_id)
        result = await client.delete(redis_key)
        return bool(result)

    # Health Check
    async def ping(self) -> bool:
        """Check if Redis is reachable.

        Returns:
            True if Redis is connected, False otherwise
        """
        try:
            client = await self._get_client()
            return await client.ping()
        except redis.RedisError:
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Global instance for use across the application
_storage: Optional[RedisStorage] = None


def get_storage() -> RedisStorage:
    """Get the global Redis storage instance (singleton).

    Returns:
        RedisStorage instance
    """
    global _storage
    if _storage is None:
        _storage = RedisStorage()
    return _storage
