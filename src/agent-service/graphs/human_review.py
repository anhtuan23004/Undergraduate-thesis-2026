"""Human Review Node for multi-agent workflow.

This module implements the HumanReviewNode which serves as a virtual
interrupt point in the workflow. The graph is compiled with
interrupt_before=["human_review"], so execution pauses BEFORE this node runs.

After a human provides feedback via the API (updating `human_review_result`
in state), the graph resumes and this node executes as a no-op.
All routing logic lives in the conditional edge (route_after_human_review).
"""

from typing import Any

import structlog

from graphs.state import GraphState

logger = structlog.get_logger()


class HumanReviewNode:
    """Node for human-in-the-loop review in the workflow.

    This node represents a human review step where a human reviewer evaluates
    the claim based on agent outputs and makes a decision.

    The graph is compiled with interrupt_before=["human_review"], so execution
    PAUSES before this node runs. After the human provides feedback via the
    API (updating `human_review_result` in state), the graph resumes and this
    node executes as a no-op.
    """

    def __init__(self) -> None:
        """Initialize the HumanReviewNode."""
        pass

    async def run(self, state: GraphState) -> dict[str, Any]:
        """Execute the human review node (no-op).

        This node is a virtual interrupt point. The graph pauses before this
        node executes, waiting for human input via the API. When resumed,
        this node simply logs the current state and returns empty updates.

        The actual routing decision comes from the `human_review_result` field
        set via the API, which is checked by route_after_human_review().

        Args:
            state: Current graph state containing human_review_result

        Returns:
            Dictionary with current_step and history updates
        """
        human_review_result = state.get("human_review_result", {})
        decision = human_review_result.get("decision", "pending")

        logger.info(
            "[Human Review] Resuming with decision",
            decision=decision,
            reviewed_by=human_review_result.get("reviewed_by", "unknown"),
        )

        return {
            "current_step": "human_review_complete",
            "pending_human_review": False,
            "history": [{"step": "human_review", "decision": decision, "resumed": True}],
        }
