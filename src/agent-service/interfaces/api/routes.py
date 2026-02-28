import asyncio
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, BackgroundTasks

from interfaces.api.models import (
    MultiAgentRequest,
    MultiAgentResponse,
    ClaimStatusResponse,
    PendingReviewsResponse,
    PendingReviewItem,
    SubmitReviewRequest,
    SubmitReviewResponse
)
from workflow.graph import build_multi_agent_graph
from workflow.state import GraphState
from langgraph.checkpoint.memory import MemorySaver
from core.storage.redis_storage import get_storage

router = APIRouter()
logger = structlog.get_logger()

# Shared MemorySaver for state persistence across all requests
_memory = MemorySaver()

# Global graph instance compiled with checkpointer
_graph = build_multi_agent_graph(checkpointer=_memory)

# Redis storage for persistence across service restarts
_storage = get_storage()

# Claim-thread mapping is now persisted in Redis
# Key: claim_id -> Value: thread_id


async def _run_graph(claim_id: str, initial_state: GraphState, config: dict) -> None:
    """Start a fresh graph run from the initial state until the first interrupt.

    Args:
        claim_id: The claim identifier
        initial_state: Initial state for the graph
        config: Configuration with thread_id for state isolation
    """
    thread_id: str = config["configurable"]["thread_id"]
    try:
        logger.info(
            "Starting graph execution",
            claim_id=claim_id,
            thread_id=thread_id
        )
        async for _ in _graph.astream(initial_state, config, stream_mode="values"):
            pass  # Runs until interrupt_before=["human_review"] fires

        # Check if we're at the human_review interrupt
        state = await _graph.aget_state(config)
        if state and state.next and "human_review" in state.next:
            logger.info(
                "Graph interrupted for human review",
                claim_id=claim_id,
                thread_id=thread_id
            )
            # Store pending review info
            pending_data = {
                "claim_id": claim_id,
                "thread_id": thread_id,
                "policy_number": initial_state.get("policy_number", ""),
                "agent_1_result": state.values.get("agent_1_result"),
                "agent_2_result": state.values.get("agent_2_result"),
                "submitted_at": datetime.utcnow().isoformat()
            }
            await _storage.set_pending_review(claim_id, pending_data)

    except Exception as exc:
        logger.error(
            "Graph execution failed",
            claim_id=claim_id,
            thread_id=thread_id,
            error=str(exc)
        )
        # Store error in Redis for persistence
        await _storage.set_error(thread_id, str(exc))
    finally:
        # Clean up claim-thread mapping after completion or error
        await _storage.delete_claim_thread_mapping(claim_id)


async def _resume_graph(claim_id: str, config: dict) -> None:
    """Resume a previously interrupted graph run after human feedback is set.

    Args:
        claim_id: The claim identifier
        config: Configuration with thread_id for state isolation
    """
    thread_id: str = config["configurable"]["thread_id"]
    try:
        logger.info(
            "Resuming graph after human review",
            claim_id=claim_id,
            thread_id=thread_id
        )
        async for _ in _graph.astream(None, config, stream_mode="values"):
            pass  # Runs until next interrupt or END

        # Remove from pending reviews if completed
        await _storage.delete_pending_review(claim_id)

        logger.info(
            "Graph resumed and completed",
            claim_id=claim_id,
            thread_id=thread_id
        )

    except Exception as exc:
        logger.error(
            "Graph resume failed",
            claim_id=claim_id,
            thread_id=thread_id,
            error=str(exc)
        )
        await _storage.set_error(thread_id, str(exc))
    finally:
        # Clean up claim-thread mapping after completion or error
        await _storage.delete_claim_thread_mapping(claim_id)


@router.post("/multi-agent/process", response_model=MultiAgentResponse)
async def process_claim(request: MultiAgentRequest, background_tasks: BackgroundTasks) -> MultiAgentResponse:
    """Process a claim through the multi-agent workflow.

    This endpoint orchestrates a multi-agent workflow that:
    1. Performs completeness check (Agent 1)
    2. Performs quality check (Agent 2)
    3. Routes to human review if needed (interrupts before human_review)
    4. Produces final decision

    The graph runs in the background and will interrupt before human_review
    if the claim requires human attention.

    Args:
        request: MultiAgentRequest containing claim_id, input_file, and policy_number
        background_tasks: FastAPI background tasks for running graph asynchronously

    Returns:
        MultiAgentResponse with initial status (graph runs in background)

    Raises:
        HTTPException: If processing fails with 500 status code
    """
    try:
        logger.info(
            "Starting multi-agent processing",
            claim_id=request.claim_id,
            policy_number=request.policy_number
        )

        # Use claim_id as thread_id for state isolation
        thread_id = request.claim_id
        config = {"configurable": {"thread_id": thread_id}}
        
        # Store claim-thread mapping in Redis for persistence across restarts
        await _storage.set_claim_thread_mapping(request.claim_id, thread_id)

        # Initialize state — only fields declared in GraphState TypedDict
        initial_state: GraphState = {
            "claim_id": request.claim_id,
            "policy_number": request.policy_number,
            "input_file": request.input_file,
            "extracted_documents": {},
            "agent_1_result": None,
            "agent_2_result": None,
            "human_review_result": None,
            "final_result": None,
            "history": [],
            "current_step": "start",
            "should_continue": True,
            "error": None,
            "pending_human_review": False,
            "edited_agent_1_result": None,
            "edited_agent_2_result": None,
        }

        # WHY: background_tasks.add_task is used instead of asyncio.create_task
        # because asyncio.create_task returns a Task that can be GC'd if no
        # reference is kept. FastAPI's BackgroundTasks manages the lifecycle safely.
        background_tasks.add_task(_run_graph, request.claim_id, initial_state, config)

        logger.info(
            "Multi-agent processing started in background",
            claim_id=request.claim_id,
            thread_id=thread_id
        )

        return MultiAgentResponse(
            claim_id=request.claim_id,
            final_decision="PENDING",
            agent_1_result=None,
            agent_2_result=None,
            human_review_result=None,
            processing_steps=[{"step": "started", "status": "running"}]
        )

    except Exception as e:
        logger.error(
            "Error in multi-agent processing",
            claim_id=request.claim_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/status/{claim_id}", response_model=ClaimStatusResponse)
async def get_claim_status(claim_id: str) -> ClaimStatusResponse:
    """Get the current status of a claim processing.

    Status values:
      - "starting"     → graph not yet checkpointed (still spinning up)
      - "running"      → agents are currently executing
      - "interrupted"  → paused before human_review; waiting for human input
      - "finished"     → graph completed (approved, rejected, or error)
      - "error"        → background task failed

    Args:
        claim_id: The claim identifier

    Returns:
        ClaimStatusResponse with current state and results

    Raises:
        HTTPException: If claim not found or error retrieving state
    """
    # Try to get thread_id from Redis (persisted across restarts)
    thread_id = await _storage.get_thread_by_claim(claim_id)
    
    # Fallback: check pending reviews in Redis
    if not thread_id:
        pending_review = await _storage.get_pending_review(claim_id)
        thread_id = pending_review.get("thread_id") if pending_review else None
    
    if not thread_id:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    config = {"configurable": {"thread_id": thread_id}}

    # Surface any background-task exception immediately
    error = await _storage.get_error(thread_id)
    if error:
        return ClaimStatusResponse(
            claim_id=claim_id,
            status="error",
            error=error
        )

    try:
        state = await _graph.aget_state(config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # No checkpoint yet (graph still starting up)
    if not state or not state.values:
        return ClaimStatusResponse(
            claim_id=claim_id,
            status="starting"
        )

    next_nodes = state.next  # tuple of node names waiting to execute

    if "human_review" in next_nodes:
        status = "interrupted"
        pending_review = True
    elif not next_nodes:
        status = "finished"
        pending_review = False
    else:
        status = "running"
        pending_review = False

    return ClaimStatusResponse(
        claim_id=claim_id,
        status=status,
        agent_1_result=state.values.get("agent_1_result"),
        agent_2_result=state.values.get("agent_2_result"),
        human_review_result=state.values.get("human_review_result"),
        final_result=state.values.get("final_result"),
        pending_human_review=pending_review,
        error=state.values.get("error")
    )


@router.get("/multi-agent/pending-reviews", response_model=PendingReviewsResponse)
async def get_pending_reviews() -> PendingReviewsResponse:
    """Get all claims waiting for human review.

    Returns:
        PendingReviewsResponse with list of claims requiring human attention
    """
    reviews = []
    all_pending = await _storage.get_all_pending_reviews()
    for claim_id, review_info in all_pending.items():
        reviews.append(PendingReviewItem(
            claim_id=review_info["claim_id"],
            policy_number=review_info.get("policy_number", ""),
            agent_1_result=review_info.get("agent_1_result"),
            agent_2_result=review_info.get("agent_2_result"),
            submitted_at=review_info.get("submitted_at")
        ))

    return PendingReviewsResponse(
        reviews=reviews,
        count=len(reviews)
    )


@router.post("/multi-agent/submit-review/{claim_id}", response_model=SubmitReviewResponse)
async def submit_review(
    claim_id: str,
    request: SubmitReviewRequest,
    background_tasks: BackgroundTasks
) -> SubmitReviewResponse:
    """Submit human feedback for a claim waiting for review.

    decision="approve"  → marks claim as approved; graph runs to final decision
    decision="reject"   → marks claim as rejected; graph runs to final decision
    decision="edit"     → injects feedback; graph loops back to quality check

    Args:
        claim_id: The claim identifier
        request: SubmitReviewRequest with decision and feedback

    Returns:
        SubmitReviewResponse with status and message

    Raises:
        HTTPException: If claim not found, not waiting for review, or invalid decision
    """
    pending_review = await _storage.get_pending_review(claim_id)
    if not pending_review:
        raise HTTPException(
            status_code=404,
            detail=f"Claim {claim_id} not found or not waiting for human review"
        )

    thread_id = pending_review["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Validate decision
    if request.decision not in ["approve", "reject", "edit"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{request.decision}'. Use 'approve', 'reject', or 'edit'."
        )

    # Build human_review_result
    human_review_result = {
        "decision": request.decision,
        "reason": request.feedback,
        "reviewed_by": request.reviewed_by,
        "valid": request.decision == "approve",
        "issues": [] if request.decision == "approve" else [{
            "severity": "medium",
            "message": request.feedback,
            "field": "human_review"
        }]
    }

    try:
        # Prepare state update with human decision
        state_update = {
            "human_review_result": human_review_result,
            "pending_human_review": False
        }

        # If human provided edited agent results, store them in state
        if request.edited_agent_1_result is not None:
            state_update["edited_agent_1_result"] = request.edited_agent_1_result
        if request.edited_agent_2_result is not None:
            state_update["edited_agent_2_result"] = request.edited_agent_2_result

        # Update state with human decision
        await _graph.aupdate_state(config, state_update)

        # WHY: background_tasks.add_task keeps a managed reference; asyncio.create_task
        # would allow the coroutine to be GC'd before completion.
        background_tasks.add_task(_resume_graph, claim_id, config)

        if request.decision == "approve":
            message = "Claim approved. Finalizing decision..."
        elif request.decision == "reject":
            message = "Claim rejected. Finalizing decision..."
        else:
            message = "Edits requested. Re-running quality check..."

        logger.info(
            "Human review submitted",
            claim_id=claim_id,
            decision=request.decision,
            reviewed_by=request.reviewed_by
        )

        return SubmitReviewResponse(
            claim_id=claim_id,
            status=request.decision,
            message=message
        )

    except Exception as exc:
        logger.error(
            "Failed to submit human review",
            claim_id=claim_id,
            error=str(exc)
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/multi-agent/health")
async def health() -> dict:
    """Health check for multi-agent service.

    Returns:
        dict with status and service name
    """
    return {"status": "healthy", "service": "multi-agent"}
