"""Status and health check API routes."""

from config import settings
from fastapi import APIRouter
from services.graph_service import get_graph
from services.workflow_state import build_workflow_response, extract_pause_state

from .errors import workflow_error

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
    graph = await get_graph()
    config = {"configurable": {"thread_id": run_id}}

    state = await graph.aget_state(config)

    if not state or not state.values:
        raise workflow_error(
            404, f"Không tìm thấy lượt chạy {run_id}", endpoint="/workflows/status"
        )

    values = {**state.values, "run_id": state.values.get("run_id") or run_id}
    is_pending, is_paused, pause_at = extract_pause_state(state)

    return build_workflow_response(
        values,
        is_pending,
        is_paused,
        pause_at,
        include_human_review=True,
    )


@router.get("/health")
async def health_check() -> dict:
    """Simple health check endpoint.

    Returns:
        dict: API health status and application version.
    """
    return {"status": "healthy", "version": settings.APP_VERSION}
