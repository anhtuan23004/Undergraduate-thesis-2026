"""Tests for agent factory lifecycle behavior."""

from dataclasses import dataclass

import pytest
from agents.factory import CompletenessAgentFactory, VerifierAgentFactory


@dataclass
class Message:
    content: object


class FakeLLMClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    async def invoke_agent(self, **kwargs):
        self.calls.append(kwargs)
        return {"messages": [Message(content=self.content)]}


@pytest.fixture(autouse=True)
def isolate_factory_dependencies(monkeypatch):
    audit_calls = []

    async def save_audit(**kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr("agents.factory.load_agent_skills", lambda _name: ([], "skill context"))
    monkeypatch.setattr(
        "agents.factory.load_system_prompt",
        lambda prompt_name, skill_contexts: f"prompt={prompt_name}; skills={skill_contexts}",
    )
    monkeypatch.setattr("agents.factory.save_agent_audit_log", save_audit)
    return audit_calls


@pytest.mark.asyncio
async def test_completeness_agent_node_uses_spec_metadata(isolate_factory_dependencies):
    llm = FakeLLMClient(
        """
        {
          "valid": false,
          "decision": "accept_with_edit",
          "issues": [],
          "message": "Cần sửa hồ sơ",
          "confidence_score": 0.72
        }
        """
    )
    node = CompletenessAgentFactory(llm).create_completeness_agent()

    result = await node(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "policy_number": "policy-1",
            "input_file": "claim.pdf",
            "extracted_documents": {},
        }
    )

    assert result["agent_1_result"]["decision"] == "accept_with_edit"
    assert result["current_step"] == "completed_completeness_agent"
    assert result["active_stage"] == "completeness"
    assert result["review_stage"] == "completeness"
    assert result["workflow_status"] == "running"
    assert llm.calls[0]["trace_name"] == "CompletenessAgent_claim-1"
    assert llm.calls[0]["metadata"] == {
        "run_id": "run-1",
        "claim_id": "claim-1",
        "agent_role": "completeness",
        "agent_name": "CompletenessAgent",
    }
    assert "<output_format>" in llm.calls[0]["system_prompt"]
    assert isolate_factory_dependencies[0]["step_name"] == "completeness_agent"


@pytest.mark.asyncio
async def test_verifier_agent_node_uses_spec_output_key(isolate_factory_dependencies):
    llm = FakeLLMClient(
        """
        {
          "verdict": "pass",
          "reason": "Không có mâu thuẫn",
          "contradictions": []
        }
        """
    )
    node = VerifierAgentFactory(llm).create_verifier_agent()

    result = await node(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "input_file": "claim.pdf",
            "agent_2_result": {"decision": "accept_with_edit"},
            "extracted_documents": {},
        }
    )

    assert result["verifier_result"]["verdict"] == "pass"
    assert result["current_step"] == "completed_verifier_agent"
    assert result["active_stage"] == "none"
    assert result["review_stage"] == "none"
    assert isolate_factory_dependencies[0]["agent_name"] == "VerifierAgent"
