"""Completeness Agent for multi-agent workflow.

Thin skill-based agent that validates document completeness.
Business logic is defined in config/instructions/completeness_agent.md.
Tools are declared in config/agents/completeness_check_agent.yaml.
"""

import structlog
from typing import Any, Dict

from core.base.agent import SkillAgent
from core.ports.llm_client import LLMClientInterface
from core.ports.config_loader import ConfigLoaderInterface
from workflow.state import GraphState

logger = structlog.get_logger()


class CompletenessAgent(SkillAgent):
    """Agent for checking document completeness.

    Inherits the full agentic tool-calling loop from SkillAgent.
    Tools (extract_documents, classify_benefit, check_required_documents)
    are loaded from config/agents/completeness_check_agent.yaml.
    The LLM is guided by config/instructions/completeness_agent.md.
    """

    def __init__(
        self,
        config_loader: ConfigLoaderInterface,
        llm_client: LLMClientInterface
    ) -> None:
        """Initialise CompletenessAgent from config files.

        Args:
            config_loader: Configuration loader implementation.
            llm_client: LLM client implementation.
        """
        super().__init__(
            agent_config_name="completeness_check_agent",
            instructions_name="completeness_agent",
            config_loader=config_loader,
            llm_client=llm_client,
        )

    def context_prompt(self, state: GraphState) -> str:
        """Build completeness-check prompt from graph state.

        Args:
            state: Current graph state.

        Returns:
            Task prompt string for the LLM.
        """
        input_file = state.get("input_file", "")

        return (
            f"Check completeness of the insurance claim.\n\n"
            f"Input File: {input_file}\n\n"
            f"Use the available tools to:\n"
            f"1. Extract documents from the input file\n"
            f"2. Classify the benefit type\n"
            f"3. Check if all required documents are present\n\n"
            f"Then provide your final decision as JSON."
        )

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute completeness check via skill-based agentic loop.

        Args:
            state: Current graph state.

        Returns:
            State updates with agent_1_result, current_step, history.
        """
        logger.info("[CompletenessAgent] Starting skill-based run", claim_id=state.get("claim_id"))

        try:
            result = await self._run_skill(state)

            logger.info(
                "[CompletenessAgent] Completed",
                valid=result.get("valid"),
                decision=result.get("decision"),
            )

            return {
                "agent_1_result": result,
                "current_step": "completeness_check_complete",
                "history": [{
                    "step": "completeness_agent",
                    "valid": result.get("valid", False),
                    "decision": result.get("decision"),
                    "confidence": result.get("confidence", 0.0),
                }],
            }

        except Exception as exc:
            return self.handle_agent_error(
                agent_name="CompletenessAgent",
                exc=exc,
                result_key="agent_1_result",
                step_name="completeness_agent"
            )
