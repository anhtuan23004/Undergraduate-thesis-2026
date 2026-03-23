"""Status and health check API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException

from config import settings
from .helpers import _extract_pause_state

router = APIRouter(prefix="", tags=["status"])

_compiled_graph = None


async def _get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client

        from graphs import build_claim_workflow
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        mongo_url = settings.MONGODB_URL
        if "directConnection" not in mongo_url:
            separator = "&" if "?" in mongo_url else "?"
            mongo_url += f"{separator}directConnection=true"

        client = MongoClient(mongo_url)
        checkpointer = MongoDBSaver(client, db_name=settings.MONGODB_DB)

        _compiled_graph = build_claim_workflow(
            llm_client=get_llm_client(),
            checkpointer=checkpointer,
        )
    return _compiled_graph


@router.get("/workflows/status/{run_id}")
async def get_workflow_status(run_id: str) -> dict:
    """Get the current status of a workflow run.

    Args:
        run_id: The unique identifier of the workflow run.

    Returns:
        dict: Current workflow state including step, results, and pause status.

    Raises:
        HTTPException: If the workflow run is not found.
    """
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    state = await graph.aget_state(config)

    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    values = state.values
    is_pending, is_paused, pause_at = _extract_pause_state(state)

    return {
        "run_id": run_id,
        "claim_id": values.get("claim_id"),
        "extracted_documents": values.get("extracted_documents"),
        "current_step": values.get("current_step"),
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "agent_1_result": values.get("agent_1_result"),
        "agent_2_result": values.get("agent_2_result"),
        "human_review_result": values.get("human_review_result"),
        "final_result": values.get("final_result"),
        "history": values.get("history", []),
        "error": values.get("error"),
    }


@router.get("/health")
async def health_check() -> dict:
    """Simple health check endpoint.

    Returns:
        dict: API health status and application version.
    """
    return {"status": "healthy", "version": settings.APP_VERSION}
