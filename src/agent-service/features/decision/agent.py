"""Final Agent for multi-agent workflow.

Thin skill-based agent that makes the final claim decision.
Business logic is defined in config/instructions/final_agent.md.
Tools are declared in config/agents/final_decision_agent.yaml.
"""

import structlog
from typing import Any, Dict
import json

from core.base.agent import SkillAgent
from core.ports.llm_client import LLMClientInterface
from core.ports.config_loader import ConfigLoaderInterface
from workflow.state import GraphState

logger = structlog.get_logger()


class FinalAgent(SkillAgent):
    """Agent for making the final claim processing decision.

    Inherits the full agentic tool-calling loop from SkillAgent.
    Tool (aggregate_issues) is loaded from config/agents/final_agent.yaml.
    The LLM is guided by config/instructions/final_agent.md to produce
    APPROVE / REJECT / PENDING decision based on aggregated issue analysis.
    """

    def __init__(
        self,
        config_loader: ConfigLoaderInterface,
        llm_client: LLMClientInterface
    ) -> None:
        """Initialise FinalAgent from config files.

        Args:
            config_loader: Configuration loader implementation.
            llm_client: LLM client implementation.
        """
        super().__init__(
            agent_config_name="final_agent",
            instructions_name="final_agent",
            config_loader=config_loader,
            llm_client=llm_client,
        )

    def context_prompt(self, state: GraphState) -> str:
        """Build final-decision prompt from all previous agent results.

        Args:
            state: Current graph state containing all previous results.

        Returns:
            Task prompt string for the LLM.
        """
        extracted_docs = state.get("extracted_documents") or {}

        agent_1 = state.get("agent_1_result") or {}
        agent_2 = state.get("agent_2_result") or {}
        human_review = state.get("human_review_result") or {}

        # Use human-edited results if provided
        edited_a1 = state.get("edited_agent_1_result")
        edited_a2 = state.get("edited_agent_2_result")
        effective_a1 = edited_a1 if edited_a1 is not None else agent_1
        effective_a2 = edited_a2 if edited_a2 is not None else agent_2

        def _safe_json(obj: Any) -> str:
            try:
                return json.dumps(obj, indent=2)
            except (TypeError, ValueError):
                return str(obj)

        return (
            f"Make the final decision for this insurance claim.\n\n"
            f"## Completeness Check Result (Agent 1):\n"
            f"{_safe_json(effective_a1)}\n\n"
            f"## Quality Check Result (Agent 2):\n"
            f"{_safe_json(effective_a2)}\n\n"
            f"## Human Review Result:\n"
            f"{_safe_json(human_review)}\n\n"
            f"## Claim Information:\n"
            f"Patient: {extracted_docs.get('patient_name', 'unknown')}\n"
            f"Total Amount: {extracted_docs.get('total_amount', 'unknown')}\n"
            f"Service Date: {extracted_docs.get('service_date', 'unknown')}\n\n"
            f"Use the aggregate_issues tool to get a weighted issue summary, "
            f"then make your final APPROVE / REJECT / PENDING decision. "
            f"Provide your response as JSON."
        )

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """Execute final decision via skill-based agentic loop.

        Args:
            state: Current graph state.

        Returns:
            State updates with final_result, current_step, should_continue.
        """
        logger.info("[FinalAgent] Starting skill-based run", claim_id=state.get("claim_id"))

        try:
            result = await self._run_skill(state)
            decision = result.get("decision", "PENDING")

            logger.info("[FinalAgent] Completed", decision=decision)

            return {
                "final_result": result,
                "current_step": "final_decision_complete",
                "should_continue": False,
                "history": [{
                    "step": "final_agent",
                    "decision": decision,
                    "confidence": result.get("confidence"),
                }],
            }

        except Exception as exc:
            error_result = self.handle_agent_error(
                agent_name="FinalAgent",
                exc=exc,
                result_key="final_result",
                step_name="final_agent"
            )
            # Final agent has special structure for final_result
            error_result["final_result"] = {
                "decision": "ERROR",
                "confidence": 0.0,
                "error": str(exc),
                "reasoning": f"Final agent failed: {exc}",
            }
            error_result["should_continue"] = False
            return error_result
