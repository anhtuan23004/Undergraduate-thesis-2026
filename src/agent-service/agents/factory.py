"""Agent Factory for creating skill-based LangGraph agents."""

from collections.abc import Callable
from typing import Any

import structlog
from graphs.constants import (
    STAGE_COMPLETENESS,
    STAGE_FINAL,
    STAGE_NONE,
    STAGE_QUALITY,
    STATUS_RUNNING,
)
from schemas.agent_outputs import AssessmentOutput, FinalDecisionOutput
from schemas.verifier_outputs import VerifierOutput
from tools.skill_loader import load_agent_skills

from agents.audit import save_agent_audit_log
from agents.helpers import (
    create_agent_error_state,
    create_history_entry,
    load_system_prompt,
)
from agents.output_parsing import extract_agent_content, parse_json_response
from agents.prompt_builders import (
    build_base_prompt,
    build_completeness_prompt,
    build_decision_prompt,
    build_quality_prompt,
    build_schema_output_instruction,
    build_verifier_prompt,
)

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
        schema_class: Any = None,
    ) -> Callable:
        """Create a stateful agent node using skill-based tool loading."""
        tools, skill_contexts = load_agent_skills(agent_skill_name)
        system_prompt = load_system_prompt(instructions_name, skill_contexts)

        if schema_class:
            system_prompt += build_schema_output_instruction(schema_class)

        async def agent_node(state: dict) -> dict:
            logger.info(f"Executing agent node: {agent_name}")
            prompt = self._build_prompt_from_state(state, agent_name)

            try:
                raw_result = await self.llm_client.invoke_agent(
                    prompt=prompt,
                    tools=tools,
                    system_prompt=system_prompt,
                    trace_name=f"{agent_name}_{state.get('claim_id', 'unknown')}",
                )

                if "error" in raw_result:
                    raise Exception(raw_result["error"])

                content_str = extract_agent_content(raw_result)
                parsed_result = parse_json_response(content_str)

                if schema_class:
                    try:
                        parsed_result = schema_class.model_validate(parsed_result).model_dump()
                    except Exception as ve:
                        logger.error(f"Schema validation failed for {agent_name}", error=str(ve))
                        raise Exception(f"Output schema validation error: {ve}") from ve

                history_entry = create_history_entry(
                    agent_name=agent_name,
                    prompt=prompt,
                    result=parsed_result,
                    step=agent_skill_name,
                )

                await save_agent_audit_log(
                    state=state,
                    step_name=agent_skill_name,
                    agent_name=agent_name,
                    result=parsed_result,
                )

                return {
                    output_state_key: parsed_result,
                    "history": [history_entry],
                    "current_step": f"completed_{agent_skill_name}",
                    "active_stage": _active_stage_after_agent(agent_skill_name),
                    "review_stage": _review_stage_after_agent(agent_skill_name, parsed_result),
                    "workflow_status": STATUS_RUNNING,
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
        return build_base_prompt(state, agent_name)


def _active_stage_after_agent(agent_skill_name: str) -> str:
    if agent_skill_name == "completeness_agent":
        return STAGE_COMPLETENESS
    if agent_skill_name == "quality_agent":
        return STAGE_QUALITY
    if agent_skill_name == "decision_agent":
        return STAGE_FINAL
    return STAGE_NONE


def _review_stage_after_agent(agent_skill_name: str, result: dict[str, Any]) -> str:
    if result.get("decision") != "accept_with_edit":
        return STAGE_NONE
    if agent_skill_name == "completeness_agent":
        return STAGE_COMPLETENESS
    if agent_skill_name == "quality_agent":
        return STAGE_QUALITY
    return STAGE_NONE


class CompletenessAgentFactory(AgentFactory):
    """Factory for creating the Completeness Check Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        return build_completeness_prompt(state, agent_name)

    def create_completeness_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="completeness_agent",
            instructions_name="completeness_agent",
            output_state_key="agent_1_result",
            agent_name="CompletenessAgent",
            schema_class=AssessmentOutput,
        )


class QualityAgentFactory(AgentFactory):
    """Factory for creating the Medical Quality Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        return build_quality_prompt(state, agent_name)

    def create_quality_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="quality_agent",
            instructions_name="quality_agent",
            output_state_key="agent_2_result",
            agent_name="QualityAgent",
            schema_class=AssessmentOutput,
        )


class DecisionAgentFactory(AgentFactory):
    """Factory for creating the Final Decision Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        return build_decision_prompt(state, agent_name)

    def create_decision_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="decision_agent",
            instructions_name="final_agent",
            output_state_key="final_result",
            agent_name="FinalAgent",
            schema_class=FinalDecisionOutput,
        )


class VerifierAgentFactory(AgentFactory):
    """Factory for creating the Skeptical Verifier Agent."""

    def _build_prompt_from_state(self, state: dict, agent_name: str) -> str:
        return build_verifier_prompt(state, agent_name)

    def create_verifier_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="verifier_agent",
            instructions_name="verifier_agent",
            output_state_key="verifier_result",
            agent_name="VerifierAgent",
            schema_class=VerifierOutput,
        )
