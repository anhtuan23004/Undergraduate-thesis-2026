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
    has_critical_or_high = any(
        i.get("severity") in ("critical", "high") for i in issues if isinstance(i, dict)
    )
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
        "accept_with_edit": "human_review",
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
        "accept_with_edit": "human_review",
    }
    return routing_map.get(decision, "final_decision")


def route_after_final_review(state: GraphState) -> str:
    """Route from final decision node."""
    human_result = state.get("human_review_result", {}) or {}
    decision = human_result.get("decision", "end")

    routing_map = {
        "approve": "end",
        "reject": "end",
        "edit": "quality_check",
    }
    return routing_map.get(decision, "end")


def _get_human_decision(state: GraphState) -> str:
    """Return normalized human-review decision from state."""
    result = state.get("human_review_result", {}) or {}
    return result.get("decision", "reject")


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
    else:
        return route_after_quality_review(state)

