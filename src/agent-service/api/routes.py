"""API routes for multi-agent service."""
import structlog
from fastapi import APIRouter, HTTPException

from api.models import MultiAgentRequest, MultiAgentResponse
from core.graph import build_multi_agent_graph
from core.state import GraphState

router = APIRouter()
logger = structlog.get_logger()


@router.post("/multi-agent/process", response_model=MultiAgentResponse)
async def process_claim(request: MultiAgentRequest) -> MultiAgentResponse:
    """Process a claim through the multi-agent workflow.

    This endpoint orchestrates a multi-agent workflow that:
    1. Performs completeness check (Agent 1)
    2. Performs quality check (Agent 2)
    3. Routes to human review if needed
    4. Produces final decision

    Args:
        request: MultiAgentRequest containing claim_id, input_file, and policy_number

    Returns:
        MultiAgentResponse with final decision and processing results

    Raises:
        HTTPException: If processing fails with 500 status code
    """
    try:
        logger.info(
            "Starting multi-agent processing",
            claim_id=request.claim_id,
            policy_number=request.policy_number
        )

        # Build graph (stateless per request)
        graph = build_multi_agent_graph()

        # Initialize state
        initial_state: GraphState = {
            "input_file": request.input_file,
            "extracted_documents": {},
            "agent_1_result": None,
            "agent_2_result": None,
            "human_review_result": None,
            "final_result": None,
            "history": [],
            "current_step": "start",
            "should_continue": True,
            "error": None
        }

        # Execute graph
        result = await graph.ainvoke(initial_state)

        # Check for errors
        if result.get("error"):
            logger.error(
                "Multi-agent processing failed",
                claim_id=request.claim_id,
                error=result["error"]
            )
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed: {result['error']}"
            )

        # Extract final result
        final_result = result.get("final_result", {})
        final_decision = final_result.get("decision", "PENDING")

        logger.info(
            "Multi-agent processing complete",
            claim_id=request.claim_id,
            final_decision=final_decision
        )

        return MultiAgentResponse(
            claim_id=request.claim_id,
            final_decision=final_decision,
            agent_1_result=result.get("agent_1_result"),
            agent_2_result=result.get("agent_2_result"),
            human_review_result=result.get("human_review_result"),
            processing_steps=result.get("history", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error in multi-agent processing",
            claim_id=request.claim_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/health")
async def health() -> dict:
    """Health check for multi-agent service.

    Returns:
        dict with status and service name
    """
    return {"status": "healthy", "service": "multi-agent"}
