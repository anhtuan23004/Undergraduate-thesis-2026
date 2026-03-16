"""Run-based v2 API routes for agent-service orchestration."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from langgraph.checkpoint.memory import MemorySaver

from core.storage.redis_storage import get_storage
from interfaces.api.models import (
    InterruptItem,
    ResumeDecision,
    ResumeRunRequest,
    ResumeRunResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunStatusResponse,
)
from workflow.graph import build_multi_agent_graph
from workflow.state import GraphState

router = APIRouter()
logger = structlog.get_logger()

REVIEW_INTERRUPT_NODES = {"completeness_review", "quality_review", "final_review"}

_memory = MemorySaver()
_graph = build_multi_agent_graph(checkpointer=_memory)


class HITLDecisionEngine:
    """Build and apply interrupt decisions consistently."""

    NODE_TO_STAGE = {
        "completeness_review": "completeness",
        "quality_review": "quality",
        "final_review": "final",
    }
    STAGE_TO_NODE = {v: k for k, v in NODE_TO_STAGE.items()}
    DEFAULT_ALLOWED_DECISIONS = ["approve", "reject", "edit"]

    @classmethod
    def stage_for_review_node(cls, review_node: str) -> str:
        """Map review node to API stage value."""
        return cls.NODE_TO_STAGE.get(review_node, "final")

    @staticmethod
    def build_interrupts(
        run_id: str,
        review_nodes: List[str],
        state_values: Dict[str, Any],
        created_at: str,
    ) -> List[InterruptItem]:
        """Create structured interrupt payloads from pending review nodes."""
        interrupts: List[InterruptItem] = []

        for node in review_nodes:
            if node == "completeness_review":
                stage = "completeness"
                action = "review_completeness"
                payload = {
                    "agent_result": state_values.get("agent_1_result"),
                    "claim_id": state_values.get("claim_id"),
                    "policy_number": state_values.get("policy_number"),
                }
            elif node == "quality_review":
                stage = "quality"
                action = "review_quality"
                payload = {
                    "agent_result": state_values.get("agent_2_result"),
                    "claim_id": state_values.get("claim_id"),
                    "policy_number": state_values.get("policy_number"),
                }
            else:
                stage = "final"
                action = "review_final_decision"
                payload = {
                    "final_result": state_values.get("final_result"),
                    "claim_id": state_values.get("claim_id"),
                    "policy_number": state_values.get("policy_number"),
                }

            interrupts.append(
                InterruptItem(
                    interrupt_id=f"intr_{uuid4().hex}",
                    run_id=run_id,
                    stage=stage,
                    action=action,
                    payload=payload,
                    allowed_decisions=HITLDecisionEngine.DEFAULT_ALLOWED_DECISIONS,
                    created_at=created_at,
                )
            )

        return interrupts

    @classmethod
    def validate_and_select_decision(
        cls,
        pending_review: Dict[str, Any],
        decisions: List[ResumeDecision],
    ) -> Tuple[Dict[str, Any], ResumeDecision]:
        """Validate resume request against interrupt contract and pick active decision."""
        interrupts = pending_review.get("interrupts", []) or []
        if not interrupts:
            raise ValueError("No pending interrupts found for this run")

        known_ids = {item.get("interrupt_id") for item in interrupts if item.get("interrupt_id")}
        decisions_by_id = {item.interrupt_id: item for item in decisions}
        unknown_ids = sorted(decisions_by_id.keys() - known_ids)
        if unknown_ids:
            raise ValueError(f"Unknown interrupt_id(s): {', '.join(unknown_ids)}")

        review_node = pending_review.get("review_node", "final_review")
        active_stage = cls.stage_for_review_node(review_node)
        active_interrupt = next(
            (item for item in interrupts if item.get("stage") == active_stage),
            interrupts[0],
        )

        active_interrupt_id = active_interrupt.get("interrupt_id")
        if not active_interrupt_id or active_interrupt_id not in decisions_by_id:
            raise ValueError(
                f"Missing decision for active interrupt '{active_interrupt_id or 'unknown'}'"
            )

        active_decision = decisions_by_id[active_interrupt_id]
        allowed_decisions = set(
            active_interrupt.get("allowed_decisions") or cls.DEFAULT_ALLOWED_DECISIONS
        )
        if active_decision.decision not in allowed_decisions:
            raise ValueError(
                f"Decision '{active_decision.decision}' not allowed for interrupt "
                f"'{active_interrupt_id}'"
            )

        if active_decision.decision == "edit" and active_decision.edited_payload is None:
            raise ValueError("Decision 'edit' requires edited_payload")

        return active_interrupt, active_decision

    @staticmethod
    def apply_decision_to_state(
        interrupt_id: str,
        decision: str,
        reviewed_by: str,
        comment: str,
        review_node: str,
        edited_payload: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        """Map a single decision payload into graph state update."""
        human_review_result = {
            "interrupt_id": interrupt_id,
            "stage": HITLDecisionEngine.stage_for_review_node(review_node),
            "decision": decision,
            "reason": comment,
            "reviewed_by": reviewed_by,
            "valid": decision == "approve",
            "issues": [] if decision == "approve" else [{
                "severity": "medium",
                "message": comment or f"Human decision: {decision}",
                "field": "human_review",
            }],
        }

        state_update: Dict[str, Any] = {
            "human_review_result": human_review_result,
            "pending_human_review": False,
            "history": [{
                "step": review_node,
                "interrupt_id": interrupt_id,
                "decision": decision,
                "reviewed_by": reviewed_by,
                "timestamp": _utc_now_iso(),
            }],
        }

        if decision == "edit" and edited_payload:
            if review_node == "completeness_review":
                state_update["edited_agent_1_result"] = edited_payload
            elif review_node == "quality_review":
                state_update["edited_agent_2_result"] = edited_payload
            else:
                # Final stage edit can still carry an explanatory payload for downstream logs
                state_update["final_result"] = edited_payload

        return state_update


def _utc_now_iso() -> str:
    """Return timezone-aware UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _build_pending_review_payload(
    run_id: str,
    thread_id: str,
    review_nodes: List[str],
    state_values: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a canonical pending-review payload for Redis."""
    created_at = _utc_now_iso()
    interrupts = HITLDecisionEngine.build_interrupts(
        run_id=run_id,
        review_nodes=review_nodes,
        state_values=state_values,
        created_at=created_at,
    )
    active_review_node = review_nodes[0]
    active_stage = HITLDecisionEngine.stage_for_review_node(active_review_node)
    active_interrupt = next((item for item in interrupts if item.stage == active_stage), interrupts[0])

    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "review_node": active_review_node,
        "active_interrupt_id": active_interrupt.interrupt_id,
        "claim_id": state_values.get("claim_id", ""),
        "policy_number": state_values.get("policy_number", ""),
        "interrupts": [i.model_dump() for i in interrupts],
        "submitted_at": created_at,
    }


async def _run_graph(run_id: str, initial_state: GraphState, config: dict) -> None:
    """Start a fresh run and pause on first interrupt or completion."""
    thread_id: str = config["configurable"]["thread_id"]
    storage = get_storage()

    try:
        logger.info("Starting run execution", run_id=run_id, thread_id=thread_id)
        async for _ in _graph.astream(initial_state, config, stream_mode="values"):
            pass

        state = await _graph.aget_state(config)
        next_nodes = set(state.next or ()) if state else set()
        review_nodes = sorted(next_nodes & REVIEW_INTERRUPT_NODES)

        if review_nodes:
            state_values = (state.values or {}) if state else {}
            pending_data = _build_pending_review_payload(
                run_id=run_id,
                thread_id=thread_id,
                review_nodes=review_nodes,
                state_values=state_values,
            )
            await storage.set_pending_review(run_id, pending_data)
            logger.info("Run interrupted for HITL", run_id=run_id, review_node=review_nodes[0])

    except Exception as exc:
        logger.error("Run execution failed", run_id=run_id, thread_id=thread_id, error=str(exc))
        await storage.set_error(thread_id, str(exc))


async def _resume_graph(run_id: str, config: dict) -> None:
    """Resume an interrupted run after human decisions are applied."""
    thread_id: str = config["configurable"]["thread_id"]
    storage = get_storage()

    try:
        logger.info("Resuming run after HITL", run_id=run_id, thread_id=thread_id)
        async for _ in _graph.astream(None, config, stream_mode="values"):
            pass

        state = await _graph.aget_state(config)
        next_nodes = set(state.next or ()) if state else set()
        review_nodes = sorted(next_nodes & REVIEW_INTERRUPT_NODES)

        if review_nodes:
            state_values = (state.values or {}) if state else {}
            pending_data = _build_pending_review_payload(
                run_id=run_id,
                thread_id=thread_id,
                review_nodes=review_nodes,
                state_values=state_values,
            )
            await storage.set_pending_review(run_id, pending_data)
            logger.info("Run interrupted again", run_id=run_id, review_node=review_nodes[0])
        else:
            await storage.delete_pending_review(run_id)
            logger.info("Run completed", run_id=run_id, thread_id=thread_id)

    except Exception as exc:
        logger.error("Run resume failed", run_id=run_id, thread_id=thread_id, error=str(exc))
        await storage.set_error(thread_id, str(exc))


@router.post("/runs", response_model=RunCreateResponse)
async def create_run(request: RunCreateRequest, background_tasks: BackgroundTasks) -> RunCreateResponse:
    """Create a new run and start processing in the background."""
    run_id = f"run_{uuid4().hex}"
    thread_id = run_id
    config = {"configurable": {"thread_id": thread_id}}

    storage = get_storage()
    await storage.set_claim_thread_mapping(run_id, thread_id)

    initial_state: GraphState = {
        "run_id": run_id,
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

    background_tasks.add_task(_run_graph, run_id, initial_state, config)

    now = _utc_now_iso()
    return RunCreateResponse(
        run_id=run_id,
        claim_id=request.claim_id,
        status="created",
        created_at=now,
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str) -> RunStatusResponse:
    """Get current status of a run."""
    storage = get_storage()
    thread_id = await storage.get_thread_by_claim(run_id)

    if not thread_id:
        pending_review = await storage.get_pending_review(run_id)
        thread_id = pending_review.get("thread_id") if pending_review else None

    if not thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    config = {"configurable": {"thread_id": thread_id}}

    error = await storage.get_error(thread_id)
    if error:
        return RunStatusResponse(
            run_id=run_id,
            claim_id=None,
            status="failed",
            current_stage="error",
            interrupts=[],
            error=error,
            updated_at=_utc_now_iso(),
        )

    try:
        state = await _graph.aget_state(config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not state or not state.values:
        return RunStatusResponse(
            run_id=run_id,
            claim_id=None,
            status="running",
            current_stage="starting",
            interrupts=[],
            updated_at=_utc_now_iso(),
        )

    state_values = state.values or {}
    next_nodes = set(state.next or ())
    pending_review = await storage.get_pending_review(run_id)

    if pending_review:
        status = "interrupted"
        interrupts_data = pending_review.get("interrupts", [])
        interrupts = [InterruptItem(**item) for item in interrupts_data]
    elif not next_nodes:
        status = "completed"
        interrupts = []
    else:
        status = "running"
        interrupts = []

    updated_at = _utc_now_iso()
    return RunStatusResponse(
        run_id=run_id,
        claim_id=state_values.get("claim_id"),
        status=status,
        current_stage=state_values.get("current_step", "unknown"),
        interrupts=interrupts,
        agent_1_result=state_values.get("agent_1_result"),
        agent_2_result=state_values.get("agent_2_result"),
        final_output=state_values.get("final_result"),
        final_result=state_values.get("final_result"),
        error=state_values.get("error"),
        updated_at=updated_at,
    )


@router.post("/runs/{run_id}/resume", response_model=ResumeRunResponse)
async def resume_run(
    run_id: str,
    request: ResumeRunRequest,
    background_tasks: BackgroundTasks,
) -> ResumeRunResponse:
    """Resume an interrupted run with one or more decisions."""
    storage = get_storage()
    pending_review = await storage.get_pending_review(run_id)
    if not pending_review:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found or not interrupted")

    thread_id = pending_review["thread_id"]
    review_node = pending_review.get("review_node", "final_review")
    config = {"configurable": {"thread_id": thread_id}}

    try:
        active_interrupt, decision = HITLDecisionEngine.validate_and_select_decision(
            pending_review=pending_review,
            decisions=request.decisions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    state_update = HITLDecisionEngine.apply_decision_to_state(
        interrupt_id=active_interrupt.get("interrupt_id", ""),
        decision=decision.decision,
        reviewed_by=request.reviewed_by,
        comment=decision.comment or "",
        review_node=review_node,
        edited_payload=decision.edited_payload,
    )

    try:
        await _graph.aupdate_state(config, state_update)
        await storage.delete_pending_review(run_id)
        background_tasks.add_task(_resume_graph, run_id, config)
    except Exception as exc:
        logger.error("Failed to apply resume decision", run_id=run_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    if decision.decision == "approve":
        message = "Decision approved. Run resumed."
    elif decision.decision == "reject":
        message = "Decision rejected. Run resumed to finalize with rejection context."
    else:
        message = "Decision edited. Run resumed with edited payload."

    return ResumeRunResponse(run_id=run_id, status="running", message=message)


@router.get("/health")
async def health() -> dict:
    """Health check for v2 orchestration API."""
    return {"status": "healthy", "service": "agent-service-v2"}
