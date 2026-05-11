"""Compiled LangGraph workflow lifecycle helpers."""

from typing import Any

from config import settings
from graphs import build_claim_workflow

from services.mongodb_config import get_mongodb_client_kwargs, normalize_mongodb_url

_compiled_graph: Any = None


async def get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        client = MongoClient(
            normalize_mongodb_url(settings.MONGODB_URL),
            **get_mongodb_client_kwargs(),
        )
        checkpointer = MongoDBSaver(client, db_name=settings.MONGODB_DB)

        _compiled_graph = build_claim_workflow(
            llm_client=get_llm_client(),
            checkpointer=checkpointer,
        )
    return _compiled_graph
