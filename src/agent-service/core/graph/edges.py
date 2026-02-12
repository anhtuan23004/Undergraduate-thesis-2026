"""Edge conditions for ReAct agent graph."""
from core.graph.state import AgentState


def should_continue(state: AgentState) -> str:
    """Determine if the ReAct loop should continue or end.

    Returns:
        "continue" - Continue to next iteration
        "decide" - Proceed to decision node
    """
    if state.get("error"):
        return "decide"

    if not state.get("should_continue", True):
        return "decide"

    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return "decide"

    tool_results = state.get("tool_results", [])
    unique_tools = {r.get("tool") for r in tool_results if r.get("tool")}

    if len(unique_tools) >= 2:
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

    return "continue"


def has_sufficient_confidence(state: AgentState) -> str:
    """Check if confidence is high enough for auto-approval."""
    confidence = state.get("confidence_score", 0)
    amount = state.get("amount_recommended", 0)

    if confidence >= 0.85 and amount < 50_000_000:
        return "auto_approve"

    if confidence >= 0.60:
        return "human_review"

    return "needs_review"
