"""Completeness Agent definition.
"""

import json
from typing import Any, Dict
from agents.factory import AgentFactory


class CompletenessAgentFactory(AgentFactory):
    """Factory for creating the Completeness Check Agent."""

    def _build_prompt_from_state(
        self, state: Dict[str, Any], agent_name: str
    ) -> str:
        """Build specific prompt for completeness check."""
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        input_file = state.get("input_file", "N/A")

        return f"""Audit the completeness of insurance claim {claim_id}.
Policy: {policy_number}
Input document: {input_file}

Your task is to:
1. Extract all relevant medical documents using 'extract_documents'.
2. Classify the benefit type using 'classify_benefit'.
3. Verify that all required documents for this benefit are present using 'check_required_documents'.

Current history:
{json.dumps(state.get('history', [])[-2:], indent=2)}
"""

    def create_completeness_agent(self) -> Any:
        """Create the completeness agent node."""
        return self.create_agent_with_state(
            agent_config_name="completeness_check_agent",
            instructions_name="completeness_agent",
            agent_name="CompletenessAgent",
        )
