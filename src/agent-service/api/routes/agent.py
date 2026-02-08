"""API routes for agent service."""
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import structlog
from langfuse.decorators import observe, langfuse_context

from core.graph.builder import build_claim_agent
from core.graph.state import create_initial_state
from core.memory.mongodb_checkpointer import MongoDBCheckpointer
from app.config import settings

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
async def decide(request: DecideRequest):
    """Process a claim and make a decision using ReAct agent.

    This endpoint runs the full ReAct loop:
    1. Observes extracted data
    2. Thinks about what information is needed
    3. Acts by calling appropriate tools
    4. Reflects on results
    5. Makes final decision

    Args:
        request: Claim data and context

    Returns:
        Decision with reasoning and evidence
    """
    import time
    start_time = time.time()

    try:
        # Update Langfuse trace name with claim_id for easy identification
        langfuse_context.update_current_trace(
            name=f"claim-{request.claim_id}",
            metadata={
                "claim_id": request.claim_id,
                "policy_number": request.policy_number,
                "max_iterations": request.max_iterations,
            }
        )

        # Log request
        logger.info(
            "Processing claim",
            claim_id=request.claim_id,
            policy_number=request.policy_number
        )

        # Create initial state
        state = create_initial_state(
            claim_id=request.claim_id,
            extracted_data=request.extracted_data,
            policy_number=request.policy_number,
            submission_date=request.submission_date,
            max_iterations=request.max_iterations
        )

        # Run agent
        result = await agent.ainvoke(state)

        # Calculate processing time
        processing_time = int((time.time() - start_time) * 1000)

        # Log completion
        logger.info(
            "Claim processed",
            claim_id=request.claim_id,
            decision=result.get("decision"),
            confidence=result.get("confidence_score"),
            iterations=result.get("iteration_count"),
            processing_time_ms=processing_time
        )

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


@router.get("/agent/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "ready"}


@router.get("/agent/graph")
async def get_graph_structure():
    """Get the ReAct graph structure for documentation."""
    from core.graph.builder import get_graph_visualization

    return {
        "graph": get_graph_visualization(),
        "nodes": ["observe", "think", "act", "reflect", "decide"],
        "entry_point": "observe",
        "terminal_node": "decide"
    }
