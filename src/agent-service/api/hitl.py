"""Human-in-the-Loop (HITL) Decision Engine.

Handles validation and application of human review decisions to the
multi-agent workflow state.
"""

import structlog
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = structlog.get_logger()


class HITLDecisionEngine:
    """Engine for processing human-in-the-loop decisions."""

    def __init__(self, storage: Any):
        """Initialize with state storage.

        Args:
            storage: Component for persisting pending review states.
        """
        self.storage = storage

    def validate_decision(
        self, state_data: Dict[str, Any], decision_data: Dict[str, Any]
    ) -> bool:
        """Validate that the decision matches the expected contract.

        Args:
            state_data: Current graph state from checkpoint.
            decision_data: Decision payload from the user.

        Returns:
            True if valid.
        """
        # Basic validation: must have decision field
        if "decision" not in decision_data:
            logger.error("HITL decision missing 'decision' field")
            return False

        # Check if decision is one of the allowed values
        allowed = ["approve", "reject", "edit", "request_info"]
        if decision_data["decision"] not in allowed:
            logger.error(f"Invalid HITL decision: {decision_data['decision']}")
            return False

        return True

    def apply_decision(
        self, state: Dict[str, Any], decision_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply human decision to the graph state.

        Args:
            state: Existing GraphState.
            decision_data: Decision payload (decision, reason, edited_payload).

        Returns:
            Updated state dictionary.
        """
        decision = decision_data.get("decision")
        reason = decision_data.get("reason", "No reason provided")
        edited_payload = decision_data.get("edited_payload")

        review_entry = {
            "decision": decision,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "reviewer": "human",
        }

        # Update core human_review field
        state["human_review"] = review_entry

        # If decision is 'edit', apply the edited payload back to state
        if decision == "edit" and edited_payload:
            logger.info("Applying edited payload to state")
            state.update(edited_payload)

        # Update history
        history = state.get("history", [])
        history.append({
            "agent": "HumanReviewer",
            "step": state.get("current_step", "human_review"),
            "result": review_entry,
        })
        state["history"] = history

        return state

    async def get_pending_review(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve pending review data from storage.

        Args:
            run_id: Unique identifier for the run.

        Returns:
            Pending review data or None.
        """
        return await self.storage.get(f"pending_review:{run_id}")

    async def clear_pending_review(self, run_id: str):
        """Clear pending review data after resumption.

        Args:
            run_id: Unique identifier for the run.
        """
        await self.storage.delete(f"pending_review:{run_id}")
