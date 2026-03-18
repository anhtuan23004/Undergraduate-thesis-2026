"""Quality Agent definition.
"""

import json
from typing import Any, Dict
from agents.factory import AgentFactory


class QualityAgentFactory(AgentFactory):
    """Factory for creating the Medical Quality Agent."""

    def _build_prompt_from_state(
        self, state: Dict[str, Any], agent_name: str
    ) -> str:
        """Build specific prompt for quality check."""
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        extracted = state.get("extracted_documents", {})

        return f"""Verify the medical quality and consistency for claim {claim_id}.
Policy: {policy_number}
Extracted data: {json.dumps(extracted, indent=2)}

Your task is to:
1. Validate diagnosis-procedure consistency using 'validate_consistency'.
2. Check ICD-10 code validity using 'validate_diagnosis'.
3. Identify policy exclusions using 'check_exclusion'.
4. Validate medication vs diagnosis using 'validate_medication'.

Current history:
{json.dumps(state.get('history', [])[-2:], indent=2)}
"""

    def create_quality_agent(self) -> Any:
        """Create the quality agent node."""
        return self.create_agent_with_state(
            agent_config_name="quality_check_agent",
            instructions_name="quality_agent",
            agent_name="QualityAgent",
        )
