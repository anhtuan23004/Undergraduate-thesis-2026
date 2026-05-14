"""Compiled LangGraph workflow lifecycle helpers."""

from typing import Any

from config import settings
from graphs.claim_workflow import build_claim_workflow
from mongodb_client import get_mongodb_client

from services.ocr_pipeline import get_default_ocr_pipeline

_compiled_graph: Any = None


async def get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client
        from langgraph.checkpoint.mongodb import MongoDBSaver

        checkpointer = MongoDBSaver(get_mongodb_client(), db_name=settings.MONGODB_DB)

        _compiled_graph = build_claim_workflow(
            llm_client=get_llm_client(),
            checkpointer=checkpointer,
            ocr_pipeline_provider=get_default_ocr_pipeline,
        )
    return _compiled_graph


def reset_graph() -> None:
    """Clear the cached compiled graph so shutdown cannot retain a closed client."""
    global _compiled_graph
    _compiled_graph = None
