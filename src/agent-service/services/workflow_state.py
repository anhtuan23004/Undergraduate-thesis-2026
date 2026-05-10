"""Workflow state construction and response helpers."""

from typing import Any

from graphs.constants import (
    STAGE_COMPLETENESS,
    STAGE_FINAL,
    STAGE_NONE,
    STAGE_QUALITY,
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STATUS_WAITING_HUMAN,
)
from graphs.state import GraphState


def extract_pause_state(snapshot: Any) -> tuple[bool, bool, str | None]:
    """Compute pause flags from graph snapshot."""
    next_nodes = list(snapshot.next or [])
    if not next_nodes:
        return False, False, None

    if "human_review" in next_nodes:
        return True, True, "human_review"

    return False, True, next_nodes[0]


def determine_review_stage(state: dict) -> str:
    """Determine which stage the human review is for based on current state."""
    if state.get("review_stage") and state.get("review_stage") != STAGE_NONE:
        return state["review_stage"]
    if state.get("final_result"):
        return STAGE_FINAL
    if state.get("agent_2_result"):
        return STAGE_QUALITY
    return STAGE_COMPLETENESS


def build_initial_state(
    run_id: str,
    claim_id: str,
    policy_number: str,
    input_file: str,
    extracted_documents: dict,
) -> GraphState:
    """Build the initial graph state for a new workflow run."""
    return {
        "run_id": run_id,
        "claim_id": claim_id,
        "policy_number": policy_number,
        "input_file": input_file,
        "extracted_documents": extracted_documents,
        "agent_1_result": None,
        "agent_2_result": None,
        "human_review_result": None,
        "edited_agent_1_result": None,
        "edited_agent_2_result": None,
        "final_result": None,
        "history": [],
        "current_step": "start",
        "active_stage": STAGE_COMPLETENESS,
        "review_stage": STAGE_NONE,
        "workflow_status": STATUS_RUNNING,
        "should_continue": True,
        "error": None,
        "pending_human_review": False,
    }


def build_workflow_response(
    result: dict,
    is_pending: bool,
    is_paused: bool,
    pause_at: str | None,
    *,
    include_human_review: bool = False,
) -> dict:
    """Build standardized workflow response dict."""
    workflow_status = _response_workflow_status(result, is_pending, is_paused)
    response = {
        "run_id": result.get("run_id"),
        "claim_id": result.get("claim_id"),
        "extracted_documents": result.get("extracted_documents"),
        "final_result": result.get("final_result"),
        "agent_1_result": result.get("agent_1_result"),
        "agent_2_result": result.get("agent_2_result"),
        "current_step": result.get("current_step"),
        "active_stage": result.get("active_stage", STAGE_NONE),
        "review_stage": result.get("review_stage", STAGE_NONE),
        "workflow_status": workflow_status,
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "history": result.get("history", []),
        "error": result.get("error"),
    }
    if include_human_review:
        response["human_review_result"] = result.get("human_review_result")
    return response


def _response_workflow_status(result: dict, is_pending: bool, is_paused: bool) -> str:
    """Derive response status while preserving explicit state when available."""
    if result.get("error"):
        return STATUS_ERROR
    if is_pending:
        return STATUS_WAITING_HUMAN
    if is_paused:
        return STATUS_PAUSED
    if result.get("workflow_status"):
        return result["workflow_status"]
    if result.get("final_result"):
        return STATUS_COMPLETED
    return STATUS_RUNNING
