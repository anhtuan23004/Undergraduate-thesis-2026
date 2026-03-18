"""Routing functions for the multi-agent workflow graph.

This module contains all conditional routing logic that determines
which node to execute next based on the current state of the workflow.
"""

from graphs.state import GraphState


def _get_decision_from_result(result: dict) -> str:
    """Extract the routing decision from an agent result dict.

    Agents (CompletenessAgent, QualityAgent) store their outcome as:
      - ``valid`` (bool)  – primary field set by the agent
      - ``decision`` (str) – optional, may be set by edited/human results

    Maps:
      valid=True  → "accept"
      valid=False, only low/medium issues → "accept_with_edit" (send to human)
      valid=False, any high/critical issues → "reject"

    Args:
        result: Raw agent result dict from GraphState.

    Returns:
        Decision string for use in routing maps.
    """
    if not result:
        return "reject"

    # Prefer explicit decision field (set by human edits or final agent)
    if "decision" in result and result["decision"] in ("accept", "reject", "accept_with_edit"):
        return result["decision"]

    valid = result.get("valid", False)
    if valid:
        return "accept"

    # Distinguish hard reject vs. needs-human-review based on issue severity
    issues = result.get("issues", []) or []
    has_critical_or_high = any(
        i.get("severity") in ("critical", "high") for i in issues
        if isinstance(i, dict)
    )
    return "reject" if has_critical_or_high else "accept_with_edit"


def route_after_completeness(state: GraphState) -> str:
    """Route after completeness check based on agent_1_result.

    Uses edited_agent_1_result if available (human edits take precedence).

    Args:
        state: The current GraphState containing agent_1_result.

    Returns:
        String key indicating the next node to route to:
        - ``"quality_check"``   – document complete, proceed
        - ``"final_decision"``  – hard reject (critical/high issues)
        - ``"human_review"``    – soft issues, needs human attention
    """
    # Use edited result if available, otherwise use original
    edited_result = state.get("edited_agent_1_result")
    original_result = state.get("agent_1_result") or {}
    result = edited_result if edited_result is not None else original_result
    decision = _get_decision_from_result(result)

    routing_map = {
        "accept": "quality_check",
        "reject": "final_decision",
        "accept_with_edit": "human_review"
    }
    return routing_map.get(decision, "final_decision")


def route_after_quality(state: GraphState) -> str:
    """Route after quality check based on agent_2_result.

    Uses edited_agent_2_result if available (human edits take precedence).

    Args:
        state: The current GraphState containing agent_2_result.

    Returns:
        String key indicating the next node to route to:
        - ``"final_decision"``  – accept or hard reject
        - ``"human_review"``    – soft issues, needs human attention
    """
    # Use edited result if available, otherwise use original
    edited_result = state.get("edited_agent_2_result")
    original_result = state.get("agent_2_result") or {}
    result = edited_result if edited_result is not None else original_result
    decision = _get_decision_from_result(result)

    routing_map = {
        "accept": "final_decision",
        "reject": "final_decision",
        "accept_with_edit": "human_review"
    }
    return routing_map.get(decision, "final_decision")




def _get_human_decision(state: GraphState) -> str:
    """Return normalized human-review decision from state."""
    result = state.get("human_review_result", {}) or {}
    return result.get("decision", "reject")


def route_after_completeness_review(state: GraphState) -> str:
    """Route from completeness review stage.

    approve -> quality_check
    reject  -> final_decision
    edit    -> completeness_check
    """
    decision = _get_human_decision(state)
    routing_map = {
        "approve": "quality_check",
        "reject": "final_decision",
        "edit": "completeness_check",
    }
    return routing_map.get(decision, "final_decision")


def route_after_quality_review(state: GraphState) -> str:
    """Route from quality review stage.

    approve -> final_decision
    reject  -> final_decision
    edit    -> quality_check
    """
    decision = _get_human_decision(state)
    routing_map = {
        "approve": "final_decision",
        "reject": "final_decision",
        "edit": "quality_check",
    }
    return routing_map.get(decision, "final_decision")


def route_after_final_review(state: GraphState) -> str:
    """Route from final review stage.

    approve/reject -> end
    edit           -> quality_check
    """
    decision = _get_human_decision(state)
    routing_map = {
        "approve": "end",
        "reject": "end",
        "edit": "quality_check",
    }
    return routing_map.get(decision, "end")
