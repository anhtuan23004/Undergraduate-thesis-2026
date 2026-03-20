"""Agent Factory for creating skill-based LangGraph agents."""

import structlog
from typing import Any, Callable

logger = structlog.get_logger()


class AgentFactory:
    """Factory for creating agents with skill-based tool loading."""

    def __init__(self, llm_client: Any):
        self.llm_client = llm_client

    def create_agent_with_skills(
        self,
        agent_skill_name: str,
        instructions_name: str,
        output_state_key: str,
        agent_name: str = "Agent",
    ) -> Callable:
        """Create a stateful agent node using skill-based tool loading."""
        from tools.skill_loader import load_agent_skills
        from agents.helpers import (
            load_system_prompt,
            extract_agent_content,
            parse_json_response,
        )

        tools, skill_contexts = load_agent_skills(agent_skill_name)
        system_prompt = load_system_prompt(instructions_name, skill_contexts)

        async def agent_node(state: dict) -> dict:
            logger.info(f"Executing agent node: {agent_name}")

            prompt = self._build_prompt_from_state(state, agent_name)

            raw_result = await self.llm_client.invoke_agent(
                prompt=prompt,
                tools=tools,
                system_prompt=system_prompt,
            )

            content_str = extract_agent_content(raw_result)
            parsed_result = parse_json_response(content_str)

            history_entry = {
                "agent": agent_name,
                "prompt": prompt[:200] + "...",
                "result": parsed_result,
                "step": state.get("current_step", "unknown"),
            }

            return {
                output_state_key: parsed_result,
                "history": state.get("history", []) + [history_entry],
                "current_step": f"completed_{agent_skill_name}",
            }

        return agent_node

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        """Build prompt using state data. Override in subclasses."""
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        return f"Process claim {claim_id} for policy {policy_number}"


class CompletenessAgentFactory(AgentFactory):
    """Factory for creating the Completeness Check Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        import json

        return f"""Audit the completeness of insurance claim {state.get("claim_id", "N/A")}.
Policy: {state.get("policy_number", "N/A")}
Input document: {state.get("input_file", "N/A")}

Current history:
{json.dumps(state.get("history", [])[-2:], indent=2)}
"""

    def create_completeness_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="completeness_agent",
            instructions_name="completeness_agent",
            output_state_key="agent_1_result",
            agent_name="CompletenessAgent",
        )


class QualityAgentFactory(AgentFactory):
    """Factory for creating the Medical Quality Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        import json

        return f"""Verify the medical quality for claim {state.get("claim_id", "N/A")}.
Policy: {state.get("policy_number", "N/A")}
Extracted data: {json.dumps(state.get("extracted_documents", {}), indent=2)}

Current history:
{json.dumps(state.get("history", [])[-2:], indent=2)}
"""

    def create_quality_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="quality_agent",
            instructions_name="quality_agent",
            output_state_key="agent_2_result",
            agent_name="QualityAgent",
        )


class DecisionAgentFactory(AgentFactory):
    """Factory for creating the Final Decision Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        import json

        return f"""Make a final decision for claim {state.get("claim_id", "N/A")}.
Policy: {state.get("policy_number", "N/A")}

Completeness: {json.dumps(state.get("agent_1_result", {}), indent=2)}
Quality: {json.dumps(state.get("agent_2_result", {}), indent=2)}
Human Review: {json.dumps(state.get("human_review_result", {}), indent=2)}
"""

    def create_decision_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="decision_agent",
            instructions_name="final_agent",
            output_state_key="final_result",
            agent_name="FinalAgent",
        )
