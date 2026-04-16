"""Workflow execution API routes."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import requests
import structlog
from config import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from graphs import build_claim_workflow
from graphs.state import GraphState
from mongodb_client import get_collection

from .helpers import (
    _determine_review_stage,
    _extract_pause_state,
    _run_ocr_document,
    _save_ocr_result,
)
from .schemas import ClaimRequest, ContinueRequest, HumanReviewRequest

logger = structlog.get_logger()

router = APIRouter(prefix="", tags=["workflows"])

_compiled_graph = None


async def _get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client
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


def _build_response(result: dict, is_pending: bool, is_paused: bool, pause_at: str | None) -> dict:
    """Build standardized workflow response dict."""
    return {
        "run_id": result.get("run_id"),
        "claim_id": result.get("claim_id"),
        "extracted_documents": result.get("extracted_documents"),
        "final_result": result.get("final_result"),
        "agent_1_result": result.get("agent_1_result"),
        "agent_2_result": result.get("agent_2_result"),
        "current_step": result.get("current_step"),
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "history": result.get("history", []),
        "error": result.get("error"),
    }


@router.post("/workflows/run")
async def run_workflow(request: ClaimRequest) -> dict:
    """Start a new claim processing workflow.

    Args:
        request: Claim processing request with claim_id, policy_number, and input_file.

    Returns:
        dict: Initial workflow state with run_id and processing status.
    """
    graph = await _get_graph()
    run_id = str(uuid.uuid4())
    ocr_result = None

    try:
        if request.file_hash:
            collection = get_collection("documents")
            existing_doc = await asyncio.to_thread(
                collection.find_one, {"file_hash": request.file_hash}
            )

            if existing_doc:
                logger.info("Using existing OCR result for hash", hash=request.file_hash)
                ocr_result = existing_doc.get("ocr_result")

                await asyncio.to_thread(
                    _save_ocr_result,
                    run_id,
                    request.claim_id,
                    request.policy_number,
                    request.input_file,
                    ocr_result,
                    request.file_hash,
                )

        if not ocr_result:
            ocr_result = await asyncio.to_thread(_run_ocr_document, request.input_file)
            await asyncio.to_thread(
                _save_ocr_result,
                run_id,
                request.claim_id,
                request.policy_number,
                request.input_file,
                ocr_result,
                request.file_hash,
            )
    except requests.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"OCR service error: {e.response.status_code if e.response else str(e)}",
        ) from e
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to connect OCR service: {str(e)}"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare OCR data: {str(e)}") from e

    initial_state: GraphState = {
        "run_id": run_id,
        "claim_id": request.claim_id,
        "policy_number": request.policy_number,
        "input_file": request.input_file,
        "extracted_documents": ocr_result,
        "agent_1_result": None,
        "agent_2_result": None,
        "human_review_result": None,
        "edited_agent_1_result": None,
        "edited_agent_2_result": None,
        "final_result": None,
        "history": [],
        "current_step": "start",
        "should_continue": True,
        "error": None,
        "pending_human_review": False,
    }

    try:
        async with asyncio.timeout(settings.PROCESS_TIMEOUT):
            config = {"configurable": {"thread_id": run_id}}
            result = await graph.ainvoke(initial_state, config=config)

            snapshot = await graph.aget_state(config)
            is_pending, is_paused, pause_at = _extract_pause_state(snapshot)

    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Processing timed out after {settings.PROCESS_TIMEOUT}s",
        ) from None

    return _build_response(result, is_pending, is_paused, pause_at)


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
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    async with asyncio.timeout(settings.PROCESS_TIMEOUT):
        current_state = await graph.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        state_values = current_state.values
        stage = _determine_review_stage(state_values)

        human_review_result = {
            "decision": request.decision,
            "notes": request.notes,
            "stage": stage,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }

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
        is_pending, is_paused, pause_at = _extract_pause_state(snapshot)

    return _build_response(result, is_pending, is_paused, pause_at)


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
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    async with asyncio.timeout(settings.PROCESS_TIMEOUT):
        current_state = await graph.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        if current_state.next and "human_review" in current_state.next:
            raise HTTPException(
                status_code=400,
                detail="Workflow is waiting for human review. Use /workflows/resume/{run_id}.",
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
        is_pending, is_paused, pause_at = _extract_pause_state(snapshot)

    return _build_response(result, is_pending, is_paused, pause_at)


# ---------------------------------------------------------------------------
# SSE Streaming helpers
# ---------------------------------------------------------------------------

# WHY: Map LangGraph node names to the UI step names used by the frontend.
_NODE_TO_STEP = {
    "completeness_check": "completeness",
    "agent_review": "agent_review",
    "quality_check": "quality",
    "human_review": "human_review",
    "final_decision": "final_decision",
}


def _sse_event(event_type: str, payload: dict) -> str:
    """Format a payload as an SSE event string.

    Args:
        event_type: SSE event name (e.g. 'node_start', 'node_end', 'done').
        payload: JSON-serialisable dict.

    Returns:
        SSE-formatted string ready to be yielded in a StreamingResponse.
    """
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {data}\n\n"


async def _stream_graph_events(
    graph: Any,
    input_state: Any,
    config: dict,
) -> AsyncGenerator[str, None]:
    """Yield SSE events while the graph executes.

    For every node that starts or finishes, an SSE event is emitted so the
    frontend can update its UI immediately.

    Args:
        graph: Compiled LangGraph workflow.
        input_state: Initial state dict (or None for resume).
        config: LangGraph config with thread_id.

    Yields:
        SSE-formatted strings for each graph event.
    """
    try:
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")
            step_key = _NODE_TO_STEP.get(name)

            if kind == "on_chain_start" and step_key:
                yield _sse_event("node_start", {"step": step_key, "node": name})

            elif kind == "on_chain_end" and step_key:
                # WHY: Build a partial response from the latest snapshot so the
                # frontend can render completed steps immediately.
                snapshot = await graph.aget_state(config)
                state_values = snapshot.values if snapshot else {}
                is_pending, is_paused, pause_at = _extract_pause_state(snapshot)
                partial = _build_response(state_values, is_pending, is_paused, pause_at)
                yield _sse_event(
                    "node_end",
                    {
                        "step": step_key,
                        "node": name,
                        "state": partial,
                    },
                )

        # WHY: Send a final snapshot once the graph run completes (or pauses).
        snapshot = await graph.aget_state(config)
        state_values = snapshot.values if snapshot else {}
        is_pending, is_paused, pause_at = _extract_pause_state(snapshot)
        final = _build_response(state_values, is_pending, is_paused, pause_at)
        yield _sse_event("done", final)

    except Exception as exc:
        logger.error("Streaming error", error=str(exc))
        yield _sse_event("error", {"error": str(exc)})


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
    graph = await _get_graph()
    run_id = str(uuid.uuid4())
    ocr_result = None

    # --- OCR phase (same as /workflows/run) ---
    try:
        if request.file_hash:
            collection = get_collection("documents")
            existing_doc = await asyncio.to_thread(
                collection.find_one, {"file_hash": request.file_hash}
            )
            if existing_doc:
                logger.info("Using existing OCR result for hash", hash=request.file_hash)
                ocr_result = existing_doc.get("ocr_result")
                await asyncio.to_thread(
                    _save_ocr_result,
                    run_id,
                    request.claim_id,
                    request.policy_number,
                    request.input_file,
                    ocr_result,
                    request.file_hash,
                )

        if not ocr_result:
            ocr_result = await asyncio.to_thread(_run_ocr_document, request.input_file)
            await asyncio.to_thread(
                _save_ocr_result,
                run_id,
                request.claim_id,
                request.policy_number,
                request.input_file,
                ocr_result,
                request.file_hash,
            )
    except requests.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"OCR service error: {e.response.status_code if e.response else str(e)}",
        ) from e
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to connect OCR service: {str(e)}"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare OCR data: {str(e)}") from e

    initial_state: GraphState = {
        "run_id": run_id,
        "claim_id": request.claim_id,
        "policy_number": request.policy_number,
        "input_file": request.input_file,
        "extracted_documents": ocr_result,
        "agent_1_result": None,
        "agent_2_result": None,
        "human_review_result": None,
        "edited_agent_1_result": None,
        "edited_agent_2_result": None,
        "final_result": None,
        "history": [],
        "current_step": "start",
        "should_continue": True,
        "error": None,
        "pending_human_review": False,
    }

    config = {"configurable": {"thread_id": run_id}}

    async def event_generator() -> AsyncGenerator[str, None]:
        """Wrap the stream with an initial run_id event."""
        yield _sse_event("run_started", {"run_id": run_id, "claim_id": request.claim_id})
        async for chunk in _stream_graph_events(graph, initial_state, config):
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
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    current_state = await graph.aget_state(config)
    if not current_state or not current_state.values:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return StreamingResponse(
        _stream_graph_events(graph, None, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
