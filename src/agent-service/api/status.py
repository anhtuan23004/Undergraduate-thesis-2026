"""Status and health check API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException

from config import settings
from .helpers import _extract_pause_state, _get_graph

router = APIRouter(prefix="", tags=["status"])

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
