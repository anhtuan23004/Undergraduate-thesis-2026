"""Agent Factory for creating skill-based LangGraph agents."""

from collections.abc import Callable
from typing import Any

import structlog
from tools.skill_loader import load_agent_skills
from workflow.contracts import STATUS_RUNNING

from agents.audit import save_agent_audit_log
from agents.helpers import (
    create_agent_error_state,
    create_history_entry,
    extract_called_tools,
    extract_token_usage,
    load_system_prompt,
)
from agents.node_specs import (
    ROLE_COMPLETENESS,
    ROLE_DECISION,
    ROLE_QUALITY,
    ROLE_VERIFIER,
    AgentNodeSpec,
    agent_node_spec,
    review_stage_after_agent_result,
)
from agents.output_parsing import extract_agent_content, parse_json_response
from agents.prompt_builders import build_schema_output_instruction

logger = structlog.get_logger()


class AgentFactory:
    """Factory for creating agents with skill-based tool loading."""

    def __init__(self, llm_client: Any):
        self.llm_client = llm_client

    def create_agent_with_skills(
        self,
        spec: AgentNodeSpec,
    ) -> Callable:
        """Create a stateful agent node using skill-based tool loading."""
        tools, skill_contexts = load_agent_skills(spec.skill_name)
        system_prompt = load_system_prompt(spec.prompt_name, skill_contexts)
        system_prompt += build_schema_output_instruction(spec.schema_class)

        async def agent_node(state: dict) -> dict:
            logger.info(f"Executing agent node: {spec.display_name}")
            prompt = spec.prompt_builder(state)

            try:
                raw_result = await self.llm_client.invoke_agent(
                    prompt=prompt,
                    tools=tools,
                    system_prompt=system_prompt,
                    trace_name=f"{spec.display_name}_{state.get('claim_id', 'unknown')}",
                    metadata={
                        "run_id": str(state.get("run_id") or ""),
                        "claim_id": str(state.get("claim_id") or ""),
                        "agent_role": spec.role,
                        "agent_name": spec.display_name,
                    },
                )

                if "error" in raw_result:
                    raise Exception(raw_result["error"])

                content_str = extract_agent_content(raw_result)
                parsed_result = parse_json_response(content_str)

                try:
                    parsed_result = spec.schema_class.model_validate(parsed_result).model_dump()
                except Exception as ve:
                    logger.error(f"Schema validation failed for {spec.display_name}", error=str(ve))
                    raise Exception(f"Output schema validation error: {ve}") from ve

                history_entry = create_history_entry(
                    agent_name=spec.display_name,
                    prompt=prompt,
                    result=parsed_result,
                    step=spec.skill_name,
                    called_tools=extract_called_tools(raw_result),
                    token_usage=extract_token_usage(raw_result),
                )

                await save_agent_audit_log(
                    state=state,
                    step_name=spec.skill_name,
                    agent_name=spec.display_name,
                    result=parsed_result,
                )

                return {
                    spec.output_key: parsed_result,
                    "history": [history_entry],
                    "current_step": f"completed_{spec.skill_name}",
                    "active_stage": spec.active_stage,
                    "review_stage": review_stage_after_agent_result(spec, parsed_result),
                    "workflow_status": STATUS_RUNNING,
                }
            except Exception as e:
                logger.error(f"Error in {spec.display_name}", error=str(e))
                return create_agent_error_state(
                    agent_result_key=spec.output_key,
                    error=e,
                    state=state,
                    error_step_name=spec.skill_name,
                )

        return agent_node


class CompletenessAgentFactory(AgentFactory):
    """Factory for creating the Completeness Check Agent."""

    def create_completeness_agent(self) -> Callable:
        return self.create_agent_with_skills(agent_node_spec(ROLE_COMPLETENESS))


class QualityAgentFactory(AgentFactory):
    """Factory for creating the Medical Quality Agent."""

    def create_quality_agent(self) -> Callable:
        return self.create_agent_with_skills(agent_node_spec(ROLE_QUALITY))


class DecisionAgentFactory(AgentFactory):
    """Factory for creating the Final Decision Agent."""

    def create_decision_agent(self) -> Callable:
        return self.create_agent_with_skills(agent_node_spec(ROLE_DECISION))


class VerifierAgentFactory(AgentFactory):
    """Factory for creating the Skeptical Verifier Agent."""

    def create_verifier_agent(self) -> Callable:
        return self.create_agent_with_skills(agent_node_spec(ROLE_VERIFIER))
