"""Routing functions for the multi-agent workflow graph.

This module contains all conditional routing logic that determines
which node to execute next based on the current state of the workflow.
"""

from core.state import GraphState


def route_after_completeness(state: GraphState) -> str:
    """Route after completeness check based on agent_1_result decision.

    Args:
        state: The current GraphState containing agent_1_result.

    Returns:
        String key indicating the next node to route to:
        - "quality_check": Document is complete, proceed to quality check
        - "final_decision": Document rejected, go to final decision
        - "human_review": Document accepted with edits needed
    """
    result = state.get("agent_1_result", {})
    decision = result.get("decision", "reject")

    routing_map = {
        "accept": "quality_check",
        "reject": "final_decision",
        "accept_with_edit": "human_review"
    }
    return routing_map.get(decision, "final_decision")


def route_after_quality(state: GraphState) -> str:
    """Route after quality check based on agent_2_result decision.

    Args:
        state: The current GraphState containing agent_2_result.

    Returns:
        String key indicating the next node to route to:
        - "final_decision": Quality check passed or rejected, go to final decision
        - "human_review": Quality issues that need human review
    """
    result = state.get("agent_2_result", {})
    decision = result.get("decision", "reject")

    routing_map = {
        "accept": "final_decision",
        "reject": "final_decision",
        "accept_with_edit": "human_review"
    }
    return routing_map.get(decision, "final_decision")


def route_after_human_review(state: GraphState) -> str:
    """Route after human review based on human_review_result decision.

    Args:
        state: The current GraphState containing human_review_result.

    Returns:
        String key indicating the next node to route to:
        - "final_decision": Human approved or rejected, go to final decision
        - "quality_check": Human made edits, loop back for quality re-check
    """
    result = state.get("human_review_result", {})
    decision = result.get("decision", "reject")

    routing_map = {
        "approve": "final_decision",
        "reject": "final_decision",
        "edit": "quality_check"  # Loop back for edits
    }
    return routing_map.get(decision, "final_decision")
