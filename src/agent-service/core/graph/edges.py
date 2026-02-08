"""Edge conditions for ReAct agent graph."""
from core.graph.state import AgentState


def should_continue(state: AgentState) -> str:
    """Determine if the ReAct loop should continue or end.

    Returns:
        "continue" - Continue to next iteration
        "decide" - Proceed to decision node
    """
    # Check for errors
    if state.get("error"):
        return "decide"

    # Check if explicitly flagged to stop
    if not state.get("should_continue", True):
        return "decide"

    # Check max iterations
    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return "decide"

    # Check if we have enough information
    tool_results = state.get("tool_results", [])

    # Must have at least 2 different tools executed
    unique_tools = set(r.get("tool") for r in tool_results if r.get("tool"))
    if len(unique_tools) >= 2:
        # Check if critical tools succeeded
        has_policy = any(
            r.get("tool") == "policy_check" and not r.get("error")
            for r in tool_results
        )
        has_icd = any(
            r.get("tool") == "icd_lookup" and not r.get("error")
            for r in tool_results
        )

        if has_policy or has_icd:
            return "decide"

    # Default: continue gathering information
    return "continue"


def has_sufficient_confidence(state: AgentState) -> str:
    """Check if confidence is high enough for auto-approval."""
    confidence = state.get("confidence_score", 0)
    amount = state.get("amount_recommended", 0)

    # High confidence + low amount = auto-approve
    if confidence >= 0.85 and amount < 50_000_000:  # < 50M VND
        return "auto_approve"

    # Medium confidence = human review
    if confidence >= 0.60:
        return "human_review"

    # Low confidence = needs more info or human review
    return "needs_review"
