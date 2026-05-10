"""Workflow execution API routes."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import requests
import structlog
from config import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from schemas.agent_outputs import HumanReviewResult
from services.graph_service import get_graph
from services.ocr_service import prepare_ocr_result
from services.workflow_state import (
    build_initial_state,
    build_workflow_response,
    determine_review_stage,
    extract_pause_state,
)

from .errors import workflow_error
from .schemas import ClaimRequest, ContinueRequest, HumanReviewRequest
from .sse import sse_event, stream_graph_events

logger = structlog.get_logger()

router = APIRouter(prefix="", tags=["workflows"])


@router.post("/workflows/run")
async def run_workflow(request: ClaimRequest) -> dict:
    """Start a new claim processing workflow.

    Args:
        request: Claim processing request with claim_id, policy_number, and input_file.

    Returns:
        dict: Initial workflow state with run_id and processing status.
    """
    graph = await get_graph()
    run_id = str(uuid.uuid4())

    try:
        ocr_result = await prepare_ocr_result(
            run_id,
            request.claim_id,
            request.policy_number,
            request.input_file,
            request.file_hash,
        )
    except requests.HTTPError as e:
        raise workflow_error(
            502,
            f"OCR service error: {e.response.status_code if e.response else str(e)}",
            endpoint="/workflows/run",
        ) from e
    except requests.RequestException as e:
        raise workflow_error(
            502, f"Failed to connect OCR service: {str(e)}", endpoint="/workflows/run"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise workflow_error(
            500, f"Failed to prepare OCR data: {str(e)}", endpoint="/workflows/run"
        ) from e

    initial_state = build_initial_state(
        run_id,
        request.claim_id,
        request.policy_number,
        request.input_file,
        ocr_result,
    )

    try:
        async with asyncio.timeout(settings.PROCESS_TIMEOUT):
            config = {"configurable": {"thread_id": run_id}}
            result = await graph.ainvoke(initial_state, config=config)

            snapshot = await graph.aget_state(config)
            is_pending, is_paused, pause_at = extract_pause_state(snapshot)

    except TimeoutError:
        raise workflow_error(
            504,
            f"Processing timed out after {settings.PROCESS_TIMEOUT}s",
            endpoint="/workflows/run",
        ) from None

    return build_workflow_response(result, is_pending, is_paused, pause_at)


@router.post("/workflows/resume/{run_id}")
async def resume_workflow(run_id: str, request: HumanReviewRequest) -> dict:
    """Resume a workflow after human review decision.

    Args:
        run_id: The unique identifier of the workflow.
        request: The human review decision payload.

    Returns:
        dict: The updated state of the workflow graph.

    Raises:
        HTTPException: If the workflow run is not found or times out.
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": run_id}}

    try:
        async with asyncio.timeout(settings.PROCESS_TIMEOUT):
            current_state = await graph.aget_state(config)
            if not current_state or not current_state.values:
                raise workflow_error(404, f"Run {run_id} not found", endpoint="/workflows/resume")

            state_values = current_state.values
            stage = determine_review_stage(state_values)

            human_review_data = {
                "decision": request.decision,
                "notes": request.notes,
                "stage": stage,
                "reviewed_at": datetime.now(UTC).isoformat(),
            }

            # WHY: Validate against typed model before injecting into graph state.
            validated = HumanReviewResult.model_validate(human_review_data)
            human_review_result = validated.model_dump()

            state_update = {
                "human_review_result": human_review_result,
                "current_step": "human_review_complete",
                "history": [
                    {
                        "step": "human_review",
                        "decision": request.decision,
                        "notes": request.notes,
                        "resumed": True,
                    }
                ],
            }

            if request.decision == "edit" and request.edited_result:
                if stage == "completeness":
                    state_update["edited_agent_1_result"] = request.edited_result
                else:
                    state_update["edited_agent_2_result"] = request.edited_result

            await graph.aupdate_state(config, state_update, as_node="human_review")
            result = await graph.ainvoke(None, config=config)

            snapshot = await graph.aget_state(config)
            is_pending, is_paused, pause_at = extract_pause_state(snapshot)
    except TimeoutError:
        raise workflow_error(
            504,
            f"Processing timed out after {settings.PROCESS_TIMEOUT}s",
            endpoint="/workflows/resume",
        ) from None

    return build_workflow_response(result, is_pending, is_paused, pause_at)


@router.post("/workflows/continue/{run_id}")
async def continue_workflow(run_id: str, request: ContinueRequest | None = None) -> dict:
    """Continue a workflow paused at a non-human stage.

    Args:
        run_id: The unique identifier of the workflow.
        request: Optional continuation note.

    Returns:
        dict: The updated state of the workflow graph.

    Raises:
        HTTPException: If workflow run not found, timed out, or requires human review.
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": run_id}}

    try:
        async with asyncio.timeout(settings.PROCESS_TIMEOUT):
            current_state = await graph.aget_state(config)
            if not current_state or not current_state.values:
                raise workflow_error(404, f"Run {run_id} not found", endpoint="/workflows/continue")

            if current_state.next and "human_review" in current_state.next:
                raise workflow_error(
                    400,
                    "Workflow is waiting for human review. Use /workflows/resume/{run_id}.",
                    endpoint="/workflows/continue",
                )

            if request and request.note:
                await graph.aupdate_state(
                    config,
                    {
                        "history": [
                            {
                                "step": "manual_continue",
                                "note": request.note,
                            }
                        ]
                    },
                )

            result = await graph.ainvoke(None, config=config)
            snapshot = await graph.aget_state(config)
            is_pending, is_paused, pause_at = extract_pause_state(snapshot)
    except TimeoutError:
        raise workflow_error(
            504,
            f"Processing timed out after {settings.PROCESS_TIMEOUT}s",
            endpoint="/workflows/continue",
        ) from None

    return build_workflow_response(result, is_pending, is_paused, pause_at)


# ---------------------------------------------------------------------------
# SSE Streaming endpoints
# ---------------------------------------------------------------------------


@router.post("/workflows/run-stream")
async def run_workflow_stream(request: ClaimRequest) -> StreamingResponse:
    """Start a new workflow and stream node-level progress via SSE.

    Args:
        request: Claim processing request.

    Returns:
        StreamingResponse with SSE events for each graph node.
    """
    graph = await get_graph()
    run_id = str(uuid.uuid4())

    try:
        ocr_result = await prepare_ocr_result(
            run_id,
            request.claim_id,
            request.policy_number,
            request.input_file,
            request.file_hash,
        )
    except requests.HTTPError as e:
        raise workflow_error(
            502,
            f"OCR service error: {e.response.status_code if e.response else str(e)}",
            endpoint="/workflows/run-stream",
        ) from e
    except requests.RequestException as e:
        raise workflow_error(
            502, f"Failed to connect OCR service: {str(e)}", endpoint="/workflows/run-stream"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise workflow_error(
            500, f"Failed to prepare OCR data: {str(e)}", endpoint="/workflows/run-stream"
        ) from e

    initial_state = build_initial_state(
        run_id,
        request.claim_id,
        request.policy_number,
        request.input_file,
        ocr_result,
    )

    config = {"configurable": {"thread_id": run_id}}

    async def event_generator() -> AsyncGenerator[str, None]:
        """Wrap the stream with an initial run_id event."""
        yield sse_event("run_started", {"run_id": run_id, "claim_id": request.claim_id})
        async for chunk in stream_graph_events(graph, initial_state, config):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/workflows/stream/{run_id}")
async def stream_workflow(run_id: str) -> StreamingResponse:
    """Stream SSE events for an existing (resumed / continued) workflow.

    Args:
        run_id: The unique workflow run identifier.

    Returns:
        StreamingResponse with SSE events for each graph node.
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": run_id}}

    current_state = await graph.aget_state(config)
    if not current_state or not current_state.values:
        raise workflow_error(404, f"Run {run_id} not found", endpoint="/workflows/stream")

    return StreamingResponse(
        stream_graph_events(graph, None, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
