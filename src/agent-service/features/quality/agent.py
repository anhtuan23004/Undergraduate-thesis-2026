"""Quality Agent for multi-agent workflow.

Thin skill-based agent that validates document quality and consistency.
Business logic is defined in config/instructions/quality_agent.md.
Tools are declared in config/agents/quality_check_agent.yaml.
"""

import structlog
from typing import Any, Dict

from core.base.agent import SkillAgent
from core.ports.llm_client import LLMClientInterface
from core.ports.config_loader import ConfigLoaderInterface
from workflow.state import GraphState

logger = structlog.get_logger()


class QualityAgent(SkillAgent):
    """Agent for validating claim quality and consistency.

    Inherits the full agentic tool-calling loop from SkillAgent.
    Tools (validate_consistency, validate_diagnosis, check_exclusion,
    validate_medication) are loaded from config/agents/quality_check_agent.yaml.
    The LLM is guided by config/instructions/quality_agent.md.
    """

    def __init__(
        self,
        config_loader: ConfigLoaderInterface,
        llm_client: LLMClientInterface
    ) -> None:
        """Initialise QualityAgent from config files.

        Args:
            config_loader: Configuration loader implementation.
            llm_client: LLM client implementation.
        """
        super().__init__(
            agent_config_name="quality_check_agent",
            instructions_name="quality_agent",
            config_loader=config_loader,
            llm_client=llm_client,
        )

    def context_prompt(self, state: GraphState) -> str:
        """Build quality-check prompt from graph state.

        Args:
            state: Current graph state.

        Returns:
            Task prompt string for the LLM.
        """
        extracted_docs = state.get("extracted_documents") or {}

        # Summarise key fields from extracted documents
        diagnosis_codes = extracted_docs.get("diagnosis_codes", [])
        medications = extracted_docs.get("medications", [])
        procedures = extracted_docs.get("procedures", [])
        benefit_category = (state.get("agent_1_result") or {}).get("benefit_category", "unknown")

        return (
            f"Validate the quality and consistency of this insurance claim.\n\n"
            f"Benefit Category: {benefit_category}\n"
            f"Diagnosis Codes: {diagnosis_codes}\n"
            f"Medications: {medications}\n"
            f"Procedures: {procedures}\n\n"
            f"Extracted Document Data:\n{extracted_docs}\n\n"
            f"Use the available tools to validate consistency, diagnoses, "
            f"exclusions, and medications. Then provide your final decision as JSON."
        )

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute quality check via skill-based agentic loop.

        Args:
            state: Current graph state.

        Returns:
            State updates with agent_2_result, current_step, history.
        """
        logger.info("[QualityAgent] Starting skill-based run", claim_id=state.get("claim_id"))

        try:
            result = await self._run_skill(state)

            logger.info(
                "[QualityAgent] Completed",
                valid=result.get("valid"),
                decision=result.get("decision"),
            )

            return {
                "agent_2_result": result,
                "current_step": "quality_check_complete",
                "history": [{
                    "step": "quality_agent",
                    "valid": result.get("valid", False),
                    "decision": result.get("decision"),
                    "confidence": result.get("confidence", 0.0),
                }],
            }

        except Exception as exc:
            return self.handle_agent_error(
                agent_name="QualityAgent",
                exc=exc,
                result_key="agent_2_result",
                step_name="quality_agent"
            )
