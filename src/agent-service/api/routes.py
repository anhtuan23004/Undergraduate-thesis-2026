"""Workflow API routes using LangGraph workflow with MongoDB persistence."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from graphs import build_claim_workflow
from graphs.state import GraphState

router = APIRouter(prefix="/api/v2", tags=["workflows"])

PROCESS_TIMEOUT = 300

_compiled_graph = None
_mongo_checkpointer = None


async def _get_mongo_checkpointer() -> Any:
    """Get or create MongoDB checkpointer."""
    global _mongo_checkpointer
    if _mongo_checkpointer is None:
        from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(settings.MONGODB_URL)
        _mongo_checkpointer = AsyncMongoDBSaver(client[settings.MONGODB_DB])
        await _mongo_checkpointer.setup()
    return _mongo_checkpointer


async def _get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client

        checkpointer = await _get_mongo_checkpointer()
        _compiled_graph = build_claim_workflow(
            llm_client=get_llm_client(),
            checkpointer=checkpointer,
        )
    return _compiled_graph


class ClaimRequest(BaseModel):
    """Request model for claim processing."""

    claim_id: str = Field(..., description="Claim identifier")
    policy_number: str = Field(..., description="Policy number")
    input_file: str = Field(..., description="Path to input document")
    extracted_documents: dict = Field(default={}, description="Pre-extracted OCR data")


class HumanReviewRequest(BaseModel):
    """Request model for human review decision."""

    decision: str = Field(..., description="Decision: approve, reject, or edit")
    notes: Optional[str] = Field(default=None, description="Reviewer notes")
    edited_result: Optional[dict] = Field(
        default=None, description="Edited agent result if decision is edit"
    )


@router.post("/workflows/run")
async def run_workflow(request: ClaimRequest) -> dict:
    """Start a new claim processing workflow."""
    graph = await _get_graph()
    run_id = str(uuid.uuid4())

    initial_state: GraphState = {
        "run_id": run_id,
        "claim_id": request.claim_id,
        "policy_number": request.policy_number,
        "input_file": request.input_file,
        "extracted_documents": request.extracted_documents,
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
        async with asyncio.timeout(PROCESS_TIMEOUT):
            config = {"configurable": {"thread_id": run_id}}
            result = await graph.ainvoke(initial_state, config=config)

            # Check if workflow is interrupted and pending human review
            snapshot = await graph.aget_state(config)
            is_pending = bool(snapshot.next and "human_review" in snapshot.next)

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Processing timed out after {PROCESS_TIMEOUT}s",
        )

    return {
        "run_id": run_id,
        "claim_id": result.get("claim_id"),
        "final_result": result.get("final_result"),
        "agent_1_result": result.get("agent_1_result"),
        "agent_2_result": result.get("agent_2_result"),
        "current_step": result.get("current_step"),
        "pending_human_review": is_pending,
        "history": result.get("history", []),
        "error": result.get("error"),
    }


@router.post("/workflows/resume/{run_id}")
async def resume_workflow(run_id: str, request: HumanReviewRequest) -> dict:
    """Resume a workflow after human review decision."""
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    async with asyncio.timeout(PROCESS_TIMEOUT):
        current_state = await graph.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        state_values = current_state.values
        stage = _determine_review_stage(state_values)

        human_review_result = {
            "decision": request.decision,
            "notes": request.notes,
            "stage": stage,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
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

        # Check if it interrupted again (e.g. loops back into another review)
        snapshot = await graph.aget_state(config)
        is_pending = bool(snapshot.next and "human_review" in snapshot.next)

    return {
        "run_id": run_id,
        "claim_id": result.get("claim_id"),
        "final_result": result.get("final_result"),
        "current_step": result.get("current_step"),
        "pending_human_review": is_pending,
        "history": result.get("history", []),
        "error": result.get("error"),
    }


def _determine_review_stage(state: dict) -> str:
    """Determine which stage the human review is for based on the current step."""
    current_step = state.get("current_step", "")
    if "quality" in current_step:
        return "quality"
    return "completeness"


@router.get("/workflows/status/{run_id}")
async def get_workflow_status(run_id: str) -> dict:
    """Get the current status of a workflow run."""
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    state = await graph.aget_state(config)

    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    values = state.values
    is_pending = bool(state.next and "human_review" in state.next)

    return {
        "run_id": run_id,
        "claim_id": values.get("claim_id"),
        "current_step": values.get("current_step"),
        "pending_human_review": is_pending,
        "agent_1_result": values.get("agent_1_result"),
        "agent_2_result": values.get("agent_2_result"),
        "human_review_result": values.get("human_review_result"),
        "final_result": values.get("final_result"),
        "history": values.get("history", []),
        "error": values.get("error"),
    }


@router.get("/health")
async def health_check() -> dict:
    """Simple health check endpoint."""
    return {"status": "healthy", "version": "langgraph-mongodb"}
