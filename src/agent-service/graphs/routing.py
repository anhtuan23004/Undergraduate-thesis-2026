"""Routing functions for the multi-agent workflow graph."""

from graphs.state import GraphState


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
    has_critical_or_high = any(i.get("severity") in ("critical", "high") for i in issues if isinstance(i, dict))
    return "reject" if has_critical_or_high else "accept_with_edit"


def route_after_completeness(state: GraphState) -> str:
    """Route after completeness check based on agent_1_result."""
    edited_result = state.get("edited_agent_1_result")
    original_result = state.get("agent_1_result") or {}
    result = edited_result if edited_result is not None else original_result
    decision = _get_decision_from_result(result)

    routing_map = {
        "accept": "quality_check",
        "reject": "final_decision",
        "accept_with_edit": "agent_review",
    }
    return routing_map.get(decision, "final_decision")


def route_after_quality(state: GraphState) -> str:
    """Route after quality check based on agent_2_result."""
    edited_result = state.get("edited_agent_2_result")
    original_result = state.get("agent_2_result") or {}
    result = edited_result if edited_result is not None else original_result
    decision = _get_decision_from_result(result)

    routing_map = {
        "accept": "final_decision",
        "reject": "final_decision",
        "accept_with_edit": "agent_review",
    }
    return routing_map.get(decision, "final_decision")


def route_after_agent_review(state: GraphState) -> str:
    """Route after the agent_review node based on auto-review status.

    The agent_review node is expected to update the corresponding agent
    result with ``is_auto_reviewed=True`` when it is confident that no
    further human intervention is required. This function inspects that
    flag to decide whether to proceed to the next automated stage or
    fall back to human review:

    * For completeness-related steps, it routes to ``quality_check`` when
      ``is_auto_reviewed`` is true, otherwise to ``human_review``.
    * For quality-related steps, it routes to ``final_decision`` when
      ``is_auto_reviewed`` is true, otherwise to ``human_review``.

    Args:
        state: Current graph state.

    Returns:
        The name of the next node: either the appropriate next automated
        stage (``quality_check`` or ``final_decision``) or ``human_review``.
    """
    # WHY: The agent_review node updates the corresponding agent result
    # with is_auto_reviewed=True when it is confident. We check that flag
    # to decide whether a human still needs to intervene.
    current_step = state.get("current_step", "")

    # Determine which agent result to inspect based on the stage.
    if "completeness" in current_step:
        result = state.get("agent_1_result") or {}
        next_stage = "quality_check"
    else:
        result = state.get("agent_2_result") or {}
        next_stage = "final_decision"

    is_auto_reviewed = result.get("is_auto_reviewed", False)
    if is_auto_reviewed:
        return next_stage

    return "human_review"


def route_after_final_review(state: GraphState) -> str:
    """Route from final decision node.

    The Agent has provided a comprehensive recommendation. We now force
    human intervention for the ultimate sign-off.
    """
    final_result = state.get("final_result")

    if final_result:
        decision = final_result.get("decision", final_result.get("status"))
        # WHY: If the agent suggests an edit to the claim data, we loop back.
        if decision == "edit":
            return "quality_check"

    # WHY: By default, ALL final results (approve/reject/accept) must
    # go through human review for final sign-off before completion.
    return "human_review"


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
        "approve": "quality_check",
        "reject": "final_decision",
        "edit": "completeness_check",
    }
    return routing_map.get(decision, "final_decision")


def route_after_quality_review(state: GraphState) -> str:
    """Route from quality review stage."""
    decision = _get_human_decision(state)
    routing_map = {
        "approve": "final_decision",
        "reject": "final_decision",
        "edit": "quality_check",
    }
    return routing_map.get(decision, "final_decision")


def route_after_human_review(state: GraphState) -> str:
    """Main router from human review node to the next appropriate node based on stage."""
    result = state.get("human_review_result", {}) or {}
    stage = result.get("stage")

    if stage == "completeness":
        return route_after_completeness_review(state)
    elif stage == "quality":
        return route_after_quality_review(state)

    # WHY: If stage is None or 'final', it's the ultimate approval/rejection.
    # An 'approve' or 'reject' decision at this point ends the workflow.
    decision = _get_human_decision(state)
    if decision in ("approve", "reject"):
        return "end"

    # If the human still wants an edit at the final stage, loop back to quality.
    return "quality_check"
