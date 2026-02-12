"""API routes for agent service."""
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from langfuse.decorators import langfuse_context, observe
from pydantic import BaseModel, Field

from app.config import settings
from core.graph.builder import build_claim_agent, get_graph_visualization
from core.graph.state import create_initial_state
from core.memory.mongodb_checkpointer import MongoDBCheckpointer

router = APIRouter()
logger = structlog.get_logger()

# Initialize checkpointer and agent
checkpointer = MongoDBCheckpointer(
    mongodb_url=settings.MONGODB_URL,
    db_name=settings.MONGODB_DB
)
agent = build_claim_agent(checkpointer=checkpointer)


class DecideRequest(BaseModel):
    """Request for claim decision."""
    claim_id: str = Field(..., description="Unique claim identifier")
    extracted_data: dict = Field(..., description="Extracted document data")
    policy_number: str = Field(..., description="Insurance policy number")
    submission_date: Optional[str] = Field(None, description="Submission date (ISO 8601)")
    max_iterations: int = Field(10, ge=1, le=20, description="Maximum ReAct iterations")


class DecideResponse(BaseModel):
    """Response from claim decision."""
    claim_id: str
    decision: str
    confidence_score: float
    amount_recommended: float
    reasoning: str
    evidence: list
    risks: list
    iterations: int
    processing_time_ms: Optional[int] = None


@router.post("/agent/decide", response_model=DecideResponse)
@observe()
async def decide(request: DecideRequest) -> DecideResponse:
    """Process a claim and make a decision using ReAct agent."""
    import time
    start_time = time.time()

    try:
        _update_langfuse_trace(request)
        _log_claim_start(request)

        state = create_initial_state(
            claim_id=request.claim_id,
            extracted_data=request.extracted_data,
            policy_number=request.policy_number,
            submission_date=request.submission_date,
            max_iterations=request.max_iterations
        )

        result = await agent.ainvoke(state)
        processing_time = int((time.time() - start_time) * 1000)

        _log_claim_complete(request, result, processing_time)

        return DecideResponse(
            claim_id=result["claim_id"],
            decision=result.get("decision", "PENDING"),
            confidence_score=result.get("confidence_score", 0.0),
            amount_recommended=result.get("amount_recommended", 0.0),
            reasoning=result.get("reasoning", ""),
            evidence=result.get("evidence", []),
            risks=result.get("risks", []),
            iterations=result.get("iteration_count", 0),
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(
            "Error processing claim",
            claim_id=request.claim_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


def _update_langfuse_trace(request: DecideRequest) -> None:
    """Update Langfuse trace with claim metadata."""
    langfuse_context.update_current_trace(
        name=f"claim-{request.claim_id}",
        metadata={
            "claim_id": request.claim_id,
            "policy_number": request.policy_number,
            "max_iterations": request.max_iterations,
        }
    )


def _log_claim_start(request: DecideRequest) -> None:
    """Log the start of claim processing."""
    logger.info(
        "Processing claim",
        claim_id=request.claim_id,
        policy_number=request.policy_number
    )


def _log_claim_complete(request: DecideRequest, result: dict, processing_time: int) -> None:
    """Log the completion of claim processing."""
    logger.info(
        "Claim processed",
        claim_id=request.claim_id,
        decision=result.get("decision"),
        confidence=result.get("confidence_score"),
        iterations=result.get("iteration_count"),
        processing_time_ms=processing_time
    )


@router.get("/agent/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "agent": "ready"}


@router.get("/agent/graph")
async def get_graph_structure() -> dict:
    """Get the ReAct graph structure for documentation."""
    return {
        "graph": get_graph_visualization(),
        "nodes": ["observe", "think", "act", "reflect", "decide"],
        "entry_point": "observe",
        "terminal_node": "decide"
    }
