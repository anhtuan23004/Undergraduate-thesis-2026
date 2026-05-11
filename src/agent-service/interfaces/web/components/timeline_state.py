"""Pure workflow timeline state helpers."""

from __future__ import annotations

from .constants import STEP_ORDER, StepStatus, UIState


def get_ui_state(state_data: dict | None) -> UIState:
    """Map graph state into one of the four UI states."""
    if not state_data:
        return UIState.PROCESSING
    workflow_status = str(state_data.get("workflow_status") or "").lower()
    if state_data.get("error"):
        return UIState.ERROR
    if workflow_status == "error":
        return UIState.ERROR
    if workflow_status == "waiting_human":
        return UIState.WAITING_FOR_HUMAN
    if workflow_status == "completed":
        return UIState.COMPLETED
    if state_data.get("final_result"):
        return UIState.COMPLETED
    if state_data.get("pending_human_review"):
        return UIState.WAITING_FOR_HUMAN
    return UIState.PROCESSING


def compute_timeline_status(state_data: dict) -> dict[str, StepStatus]:
    """Compute timeline status from explicit workflow state fields."""
    out = dict.fromkeys(STEP_ORDER, StepStatus.PENDING)

    if _apply_completed_status(out, state_data):
        return out
    if _apply_waiting_status(out, state_data):
        return out

    _apply_active_status(out, state_data)
    return out


def _apply_completed_status(out: dict[str, StepStatus], state_data: dict) -> bool:
    if state_data.get("agent_1_result"):
        out["completeness"] = StepStatus.DONE
    if _has_agent_review(state_data):
        out["agent_review"] = StepStatus.DONE
    if state_data.get("agent_2_result"):
        out["quality"] = StepStatus.DONE
    if state_data.get("human_review_result") and not state_data.get("pending_human_review"):
        out["human_review"] = StepStatus.DONE
    if state_data.get("final_result"):
        out["final_decision"] = StepStatus.DONE
        return True
    return False


def _apply_waiting_status(out: dict[str, StepStatus], state_data: dict) -> bool:
    workflow_status = str(state_data.get("workflow_status") or "").lower()
    if workflow_status != "waiting_human" and not state_data.get("pending_human_review"):
        return False

    review_stage = str(state_data.get("review_stage") or "").lower()
    out["human_review"] = StepStatus.WAITING
    if review_stage in {"completeness", "quality"}:
        out["agent_review"] = StepStatus.DONE
    return True


def _apply_active_status(out: dict[str, StepStatus], state_data: dict) -> None:
    active_stage = str(state_data.get("active_stage") or "").lower()
    workflow_status = str(state_data.get("workflow_status") or "").lower()

    if active_stage == "completeness":
        out["completeness"] = StepStatus.ACTIVE
    elif active_stage == "quality":
        out["quality"] = StepStatus.ACTIVE
        _mark_agent_review_done(out)
    elif active_stage == "final":
        out["final_decision"] = StepStatus.ACTIVE
        _mark_agent_review_done(out)
    elif workflow_status == "running" and out["completeness"] == StepStatus.PENDING:
        out["completeness"] = StepStatus.ACTIVE
    elif _is_agent_review_active(out, workflow_status):
        out["agent_review"] = StepStatus.ACTIVE


def _mark_agent_review_done(out: dict[str, StepStatus]) -> None:
    if out["agent_review"] != StepStatus.DONE:
        out["agent_review"] = StepStatus.DONE


def _is_agent_review_active(out: dict[str, StepStatus], workflow_status: str) -> bool:
    return (
        workflow_status == "running"
        and out["completeness"] == StepStatus.DONE
        and out["quality"] == StepStatus.PENDING
    )


def _has_agent_review(state_data: dict) -> bool:
    history = state_data.get("history") or []
    if any(item.get("step") == "agent_review" for item in history if isinstance(item, dict)):
        return True

    agent_1_result = state_data.get("agent_1_result") or {}
    agent_2_result = state_data.get("agent_2_result") or {}
    return (
        agent_1_result.get("is_auto_reviewed") is not None
        or agent_2_result.get("is_auto_reviewed") is not None
    )


_compute_timeline_status = compute_timeline_status
