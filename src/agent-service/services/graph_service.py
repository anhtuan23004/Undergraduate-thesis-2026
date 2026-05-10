"""Compiled LangGraph workflow lifecycle helpers."""

from typing import Any

from config import settings
from graphs import build_claim_workflow

_compiled_graph: Any = None


def normalize_mongodb_url(mongo_url: str) -> str:
    """Ensure MongoDB URL uses direct connection for local checkpointing."""
    if "directConnection" in mongo_url:
        return mongo_url
    separator = "&" if "?" in mongo_url else "?"
    return f"{mongo_url}{separator}directConnection=true"


async def get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        client = MongoClient(normalize_mongodb_url(settings.MONGODB_URL))
        checkpointer = MongoDBSaver(client, db_name=settings.MONGODB_DB)

        _compiled_graph = build_claim_workflow(
            llm_client=get_llm_client(),
            checkpointer=checkpointer,
        )
    return _compiled_graph
