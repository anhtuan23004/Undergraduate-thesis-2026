"""Routing functions for the multi-agent workflow graph."""

from graphs.constants import (
    AGENT_REVIEW,
    COMPLETENESS_CHECK,
    END,
    FINAL_DECISION,
    HUMAN_REVIEW,
    OCR_EXTRACTION,
    QUALITY_CHECK,
    SEVERITY_ESCALATION,
    STAGE_COMPLETENESS,
    STAGE_FINAL,
    STAGE_NONE,
    STAGE_QUALITY,
)
from graphs.state import GraphState

OCR_STAGE_PHASE1_CLASSIFIED = "phase1_classified"


def _get_decision_from_result(result: dict) -> str:
    """Extract the routing decision from an agent result dict."""
    if not result:
        return "reject"

    if "decision" in result:
        if result["decision"] in ("accept", "reject", "accept_with_edit"):
            return result["decision"]

    valid = result.get("valid", False)
    if valid:
        return "accept"

    issues = result.get("issues", []) or []
    has_critical_or_high = any(
        i.get("severity") in SEVERITY_ESCALATION for i in issues if isinstance(i, dict)
    )
    return "reject" if has_critical_or_high else "accept_with_edit"


def route_after_completeness(state: GraphState) -> str:
    """Route after completeness check based on agent_1_result."""
    edited_result = state.get("edited_agent_1_result")
    original_result = state.get("agent_1_result") or {}
    result = edited_result if edited_result is not None else original_result
    decision = _get_decision_from_result(result)

    routing_map = {
        "accept": _route_after_completeness_success(state),
        "reject": FINAL_DECISION,
        "accept_with_edit": AGENT_REVIEW,
    }
    return routing_map.get(decision, FINAL_DECISION)


def route_after_quality(state: GraphState) -> str:
    """Route after quality check based on agent_2_result."""
    edited_result = state.get("edited_agent_2_result")
    original_result = state.get("agent_2_result") or {}
    result = edited_result if edited_result is not None else original_result
    decision = _get_decision_from_result(result)

    routing_map = {
        "accept": FINAL_DECISION,
        "reject": FINAL_DECISION,
        "accept_with_edit": AGENT_REVIEW,
    }
    return routing_map.get(decision, FINAL_DECISION)


def route_after_agent_review(state: GraphState) -> str:
    """Route after the agent_review node based on auto-review status.

    The agent_review node is expected to update the corresponding agent
    result with ``is_auto_reviewed=True`` when it is confident that no
    further human intervention is required. This function inspects that
    flag to decide whether to proceed to the next automated stage or
    fall back to human review:

    * For completeness-related steps, it routes by OCR stage when
      ``is_auto_reviewed`` is true, otherwise to ``human_review``.
    * For quality-related steps, it routes to ``final_decision`` when
      ``is_auto_reviewed`` is true, otherwise to ``human_review``.

    Args:
        state: Current graph state.

    Returns:
        The name of the next node: either the appropriate next automated
        stage (``ocr_extraction``, ``quality_check``, or ``final_decision``)
        or ``human_review``.
    """
    # WHY: The agent_review node updates the corresponding agent result
    # with is_auto_reviewed=True when it is confident. We check that flag
    # to decide whether a human still needs to intervene.
    review_stage = _review_stage_from_state(state)
    if review_stage == STAGE_COMPLETENESS:
        result = state.get("agent_1_result") or {}
        next_stage = _route_after_completeness_success(state)
    else:
        result = state.get("agent_2_result") or {}
        next_stage = FINAL_DECISION

    is_auto_reviewed = result.get("is_auto_reviewed", False)
    if is_auto_reviewed:
        return next_stage

    return HUMAN_REVIEW


def route_after_final_review(state: GraphState) -> str:
    """Route from final decision node.

    The DecisionAgent has provided a comprehensive recommendation. We now
    force human intervention for the ultimate sign-off. The DecisionAgent
    schema only allows ``approve`` or ``reject``, so all paths lead to
    ``human_review``.
    """
    # WHY: FinalDecisionOutput.decision is Literal["approve", "reject"].
    # No "edit" branch exists for the final agent — all results require
    # human sign-off before the workflow can complete.
    return HUMAN_REVIEW


def _get_human_decision(state: GraphState) -> str:
    """Return normalized human-review decision from state.

    Supports 'accept', 'approve', 'reject', 'edit'.
    """
    result = state.get("human_review_result", {}) or {}
    decision = str(result.get("decision", "reject")).lower()

    if decision in ("accept", "approve"):
        return "approve"
    if decision in ("reject", "denied"):
        return "reject"
    if decision == "edit":
        return "edit"
    return "reject"


def route_after_completeness_review(state: GraphState) -> str:
    """Route from completeness review stage."""
    decision = _get_human_decision(state)
    routing_map = {
        "approve": _route_after_completeness_success(state),
        "reject": FINAL_DECISION,
        "edit": COMPLETENESS_CHECK,
    }
    return routing_map.get(decision, FINAL_DECISION)


def route_after_quality_review(state: GraphState) -> str:
    """Route from quality review stage."""
    decision = _get_human_decision(state)
    routing_map = {
        "approve": FINAL_DECISION,
        "reject": FINAL_DECISION,
        "edit": QUALITY_CHECK,
    }
    return routing_map.get(decision, FINAL_DECISION)


def route_after_ocr_extraction(state: GraphState) -> str:
    """Route after OCR phase 2 extraction."""
    if state.get("ocr_stage") == "phase2_extracted":
        return QUALITY_CHECK
    return FINAL_DECISION


def _route_after_completeness_success(state: GraphState) -> str:
    """Route successful completeness based on the available OCR stage."""
    if state.get("ocr_stage") == OCR_STAGE_PHASE1_CLASSIFIED:
        return OCR_EXTRACTION
    return QUALITY_CHECK


def route_after_human_review(state: GraphState) -> str:
    """Main router from human review node to the next appropriate node based on stage."""
    result = state.get("human_review_result", {}) or {}
    stage = result.get("stage") or _review_stage_from_state(state)

    if stage == STAGE_COMPLETENESS:
        return route_after_completeness_review(state)
    elif stage == STAGE_QUALITY:
        return route_after_quality_review(state)

    # WHY: If stage is None or 'final', it's the ultimate approval/rejection.
    # An 'approve' or 'reject' decision at this point ends the workflow.
    decision = _get_human_decision(state)
    if decision in ("approve", "reject"):
        return END

    # If the human still wants an edit at the final stage, loop back to quality.
    return QUALITY_CHECK


def _review_stage_from_state(state: GraphState) -> str:
    """Return explicit review stage with legacy current_step fallback."""
    explicit_stage = state.get("review_stage")
    if explicit_stage and explicit_stage != STAGE_NONE:
        return explicit_stage

    current_step = state.get("current_step", "")
    if STAGE_COMPLETENESS in current_step:
        return STAGE_COMPLETENESS
    if STAGE_QUALITY in current_step:
        return STAGE_QUALITY
    if STAGE_FINAL in current_step or state.get("final_result"):
        return STAGE_FINAL
    return STAGE_QUALITY
