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
        from agents.helpers import (
            create_agent_error_state,
            create_history_entry,
            extract_agent_content,
            load_system_prompt,
            parse_json_response,
        )
        from tools.skill_loader import load_agent_skills

        tools, skill_contexts = load_agent_skills(agent_skill_name)
        system_prompt = load_system_prompt(instructions_name, skill_contexts)

        async def agent_node(state: dict) -> dict:
            logger.info(f"Executing agent node: {agent_name}")
            prompt = self._build_prompt_from_state(state, agent_name)

            try:
                raw_result = await self.llm_client.invoke_agent(
                    prompt=prompt,
                    tools=tools,
                    system_prompt=system_prompt,
                )

                if "error" in raw_result:
                    raise Exception(raw_result["error"])

                content_str = extract_agent_content(raw_result)
                parsed_result = parse_json_response(content_str)

                history_entry = create_history_entry(
                    agent_name=agent_name,
                    prompt=prompt,
                    result=parsed_result,
                    step=state.get("current_step", "unknown"),
                )

                return {
                    output_state_key: parsed_result,
                    "history": [history_entry],
                    "current_step": f"completed_{agent_skill_name}",
                }
            except Exception as e:
                logger.error(f"Error in {agent_name}", error=str(e))
                return create_agent_error_state(
                    agent_result_key=output_state_key,
                    error=e,
                    state=state,
                    error_step_name=agent_skill_name,
                )

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

        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        input_file = state.get("input_file", "N/A")
        history = json.dumps(state.get("history", [])[-2:], indent=2)

        return (
            f"Audit the completeness of insurance claim {claim_id}.\n"
            f"Policy: {policy_number}\n"
            f"Input document: {input_file}\n\n"
            f"Current history:\n{history}\n"
        )

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

        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        extracted = json.dumps(state.get("extracted_documents", {}), indent=2)
        history = json.dumps(state.get("history", [])[-2:], indent=2)

        return (
            f"Verify the medical quality for claim {claim_id}.\n"
            f"Policy: {policy_number}\n"
            f"Extracted data: {extracted}\n\n"
            f"Current history:\n{history}\n"
        )

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

        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        completeness = json.dumps(state.get("agent_1_result", {}), indent=2)
        quality = json.dumps(state.get("agent_2_result", {}), indent=2)
        human_review = json.dumps(state.get("human_review_result", {}), indent=2)

        return (
            f"Make a final decision for claim {claim_id}.\n"
            f"Policy: {policy_number}\n\n"
            f"Completeness: {completeness}\n"
            f"Quality: {quality}\n"
            f"Human Review: {human_review}\n"
        )

    def create_decision_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="decision_agent",
            instructions_name="final_agent",
            output_state_key="final_result",
            agent_name="FinalAgent",
        )
