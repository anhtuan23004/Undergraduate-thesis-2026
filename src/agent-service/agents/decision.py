"""Final Decision Agent definition.
"""

import json
from typing import Any, Dict
from agents.factory import AgentFactory


class DecisionAgentFactory(AgentFactory):
    """Factory for creating the Final Decision Agent."""

    def _build_prompt_from_state(
        self, state: Dict[str, Any], agent_name: str
    ) -> str:
        """Build specific prompt for final decision."""
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")

        completeness_result = state.get("agent_1_result", {})
        quality_result = state.get("agent_2_result", {})
        human_review_result = state.get("human_review", {})

        return f"""Make a final decision for insurance claim {claim_id}.
Policy: {policy_number}

Completeness Check Result:
{json.dumps(completeness_result, indent=2)}

Medical Quality Result:
{json.dumps(quality_result, indent=2)}

Human Review (if any):
{json.dumps(human_review_result, indent=2)}

Your task is to:
1. Aggregate all identified issues using 'aggregate_issues'.
2. Provide a final decision (Approve/Reject/Reject with partial payment).
3. Justify your decision based on the gathered evidence.

Current history:
{json.dumps(state.get('history', [])[-2:], indent=2)}
"""

    def create_decision_agent(self) -> Any:
        """Create the final decision agent node."""
        return self.create_agent_with_state(
            agent_config_name="final_agent",
            instructions_name="final_agent",
            agent_name="FinalAgent",
        )
