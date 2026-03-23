"""Agent Factory for creating skill-based LangGraph agents."""

import structlog
import json
from typing import Any, Callable
import asyncio
from mongodb_client import get_collection
from datetime import datetime, timezone

from schemas.agent_outputs import AssessmentOutput, FinalDecisionOutput
from schemas.verifier_outputs import VerifierOutput
from agents.helpers import (
    create_agent_error_state,
    create_history_entry,
    extract_agent_content,
    load_system_prompt,
    parse_json_response,
)
from tools.skill_loader import load_agent_skills

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
            # WHY: Exclude internal fields (like is_auto_reviewed) from the LLM prompt
            # to prevent hallucination of system-level flags.
            schema_dict = schema_class.model_json_schema()
            if "properties" in schema_dict:
                schema_dict["properties"].pop("is_auto_reviewed", None)

            schema_json = json.dumps(schema_dict, ensure_ascii=False)
            system_prompt += (
                f"\n\n<output_format>\n"
                f"Bạn phải trả về kết quả tuân thủ chính xác lược đồ JSON sau:\n"
                f"{schema_json}\n</output_format>"
            )

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
                        raise Exception(f"Output schema validation error: {ve}")

                history_entry = create_history_entry(
                    agent_name=agent_name,
                    prompt=prompt,
                    result=parsed_result,
                    step=agent_skill_name,
                )

                try:

                    def _save_audit():
                        audit_col = get_collection("audit_logs")
                        audit_col.insert_one(
                            {
                                "run_id": state.get("run_id"),
                                "claim_id": state.get("claim_id"),
                                "step_name": agent_skill_name,
                                "agent_name": agent_name,
                                "result_json": parsed_result,
                                "timestamp": datetime.now(timezone.utc),
                            }
                        )

                    await asyncio.to_thread(_save_audit)
                except Exception as db_e:
                    logger.warning(f"Failed to save audit log: {db_e}")

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
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        input_file = state.get("input_file", "N/A")
        extracted = json.dumps(state.get("extracted_documents", {}), indent=2, ensure_ascii=False)
        history_list = state.get("history", [])[-2:]
        history_summary = (
            "\n".join(
                [
                    f"- Bước {h.get('step', 'unknown')} ({h.get('agent', 'System')}): Đã xử lý"
                    for h in history_list
                ]
            )
            if history_list
            else "Chưa có"
        )

        return (
            f"Kiểm toán tính đầy đủ của hồ sơ bảo hiểm {claim_id}. Số hợp đồng: {policy_number}\n"
            f"Tài liệu đầu vào: {input_file}\n\n"
            f"<extracted_documents>\n{extracted}\n</extracted_documents>\n\n"
            f"<history_summary>\n{history_summary}\n</history_summary>\n"
        )

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
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        extracted = json.dumps(state.get("extracted_documents", {}), indent=2, ensure_ascii=False)
        history_list = state.get("history", [])[-2:]
        history_summary = (
            "\n".join(
                [
                    f"- Bước {h.get('step', 'unknown')} ({h.get('agent', 'System')}): Đã xử lý"
                    for h in history_list
                ]
            )
            if history_list
            else "Chưa có"
        )

        return (
            f"Xác minh chất lượng y tế cho hồ sơ {claim_id}. Số hợp đồng: {policy_number}\n\n"
            f"<extracted_documents>\n{extracted}\n</extracted_documents>\n\n"
            f"<history_summary>\n{history_summary}\n</history_summary>\n"
        )

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
        claim_id = state.get("claim_id", "N/A")
        policy_number = state.get("policy_number", "N/A")
        completeness = json.dumps(state.get("agent_1_result", {}), indent=2, ensure_ascii=False)
        quality = json.dumps(state.get("agent_2_result", {}), indent=2, ensure_ascii=False)
        human_review = json.dumps(
            state.get("human_review_result", {}), indent=2, ensure_ascii=False
        )

        return (
            f"Đưa ra quyết định cuối cùng cho hồ sơ {claim_id}. Số hợp đồng: {policy_number}\n\n"
            f"<completeness_result>\n{completeness}\n</completeness_result>\n\n"
            f"<quality_result>\n{quality}\n</quality_result>\n\n"
            f"<human_review_result>\n{human_review}\n</human_review_result>\n"
        )

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
        claim_id = state.get("claim_id", "N/A")
        input_file = state.get("input_file", "N/A")
        current_step = state.get("current_step", "")

        # WHY: Determine which assessment to verify.
        if "completeness" in current_step:
            primary_assessment = state.get("agent_1_result", {})
        else:
            primary_assessment = state.get("agent_2_result", {})

        evidence = primary_assessment.get("evidence", {})
        extracted = json.dumps(state.get("extracted_documents", {}), indent=2, ensure_ascii=False)

        primary_json = json.dumps(primary_assessment, indent=2, ensure_ascii=False)
        evidence_json = json.dumps(evidence, indent=2, ensure_ascii=False)

        return (
            f"Thẩm định chéo kết quả đánh giá cho hồ sơ {claim_id}.\n"
            f"Tài liệu gốc: {input_file}\n\n"
            f"<primary_assessment>\n{primary_json}\n</primary_assessment>\n\n"
            f"<extracted_evidence>\n{evidence_json}\n</extracted_evidence>\n\n"
            f"<extracted_documents>\n{extracted}\n</extracted_documents>\n"
        )

    def create_verifier_agent(self) -> Callable:
        return self.create_agent_with_skills(
            agent_skill_name="verifier_agent",
            instructions_name="verifier_agent",
            output_state_key="verifier_result",
            agent_name="VerifierAgent",
            schema_class=VerifierOutput,
        )
