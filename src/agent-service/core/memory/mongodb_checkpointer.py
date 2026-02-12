"""MongoDB checkpointer for LangGraph state persistence."""
from datetime import datetime
from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from motor.motor_asyncio import AsyncIOMotorClient


class MongoDBCheckpointer(BaseCheckpointSaver):
    """Checkpointer that saves agent state to MongoDB.

    This allows the agent to:
    1. Resume from interruptions
    2. Review past executions
    3. Debug by examining state history
    """

    def __init__(self, mongodb_url: str, db_name: str = "claims"):
        """Initialize MongoDB checkpointer.

        Args:
            mongodb_url: MongoDB connection URL
            db_name: Database name
        """
        self.client = AsyncIOMotorClient(mongodb_url)
        self.db = self.client[db_name]
        self.collection = self.db["agent_checkpoints"]

    async def aget(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest checkpoint for a thread.

        Args:
            thread_id: Unique thread identifier (claim_id)

        Returns:
            The saved state or None if not found
        """
        doc = await self.collection.find_one(
            {"thread_id": thread_id},
            sort={"timestamp": -1}
        )
        return doc.get("state") if doc else None

    async def aset(
        self,
        thread_id: str,
        state: Dict[str, Any],
        **metadata
    ) -> None:
        """Save a checkpoint.

        Args:
            thread_id: Unique thread identifier (claim_id)
            state: Current agent state
            **metadata: Additional metadata to store
        """
        checkpoint = {
            "thread_id": thread_id,
            "state": state,
            "timestamp": datetime.utcnow(),
            "iteration": state.get("iteration_count", 0),
            "decision": state.get("decision"),
            "confidence": state.get("confidence_score"),
            "metadata": metadata
        }

        await self.collection.update_one(
            {"thread_id": thread_id},
            {"$set": checkpoint},
            upsert=True
        )

    async def adelete(self, thread_id: str) -> None:
        """Delete all checkpoints for a thread.

        Args:
            thread_id: Unique thread identifier
        """
        await self.collection.delete_many({"thread_id": thread_id})

    async def aget_history(
        self,
        thread_id: str,
        limit: int = 10
    ) -> list:
        """Get checkpoint history for a thread.

        Args:
            thread_id: Unique thread identifier
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint documents
        """
        cursor = self.collection.find(
            {"thread_id": thread_id}
        ).sort("timestamp", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def list_active_threads(
        self,
        limit: int = 100
    ) -> list:
        """List threads with recent activity.

        Args:
            limit: Maximum number of threads

        Returns:
            List of thread summaries
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$thread_id",
                    "last_activity": {"$max": "$timestamp"},
                    "iterations": {"$max": "$iteration"},
                    "decision": {"$last": "$decision"}
                }
            },
            {"$sort": {"last_activity": -1}},
            {"$limit": limit}
        ]

        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
