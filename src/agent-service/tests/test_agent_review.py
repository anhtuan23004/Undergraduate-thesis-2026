"""Tests for the AgentReviewNode logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from graphs.agent_review import AgentReviewNode


class TestAgentReviewNode:
    """Unit tests for the AgentReviewNode."""

    @pytest.mark.asyncio
    async def test_escalate_on_medium_issue(self, node):
        """Test that medium issues (warnings) trigger escalation."""
        state = {
            "current_step": "completeness_check",
            "agent_1_result": {
                "confidence_score": 0.95,
                "issues": [
                    {"severity": "medium", "code": "WARN_1", "description": "Minor mismatch"}
                ],
                "suggested_updates": [{"field": "date", "suggested_value": "2024-01-01"}],
                "evidence": {"total_claim_amount": 1000000},
            },
        }
        result = await node.run(state)
        assert result["pending_human_review"] is True
        assert (
            "medium" in result["history"][0]["escalation_reason"].lower()
            or "severity" in result["history"][0]["escalation_reason"].lower()
        )

    @pytest.mark.asyncio
    async def test_escalate_on_contradictions(self, node):
        """Test that even a 'pass' verdict with contradictions triggers escalation."""
        state = {
            "current_step": "completeness_check",
            "agent_1_result": {
                "confidence_score": 0.95,
                "issues": [{"severity": "low", "code": "INFO_1"}],
                "suggested_updates": [{"field": "date", "suggested_value": "2024-01-01"}],
                "evidence": {"total_claim_amount": 1000000},
            },
        }
        # Mock verifier to return pass but with contradictions
        node.verifier_agent = AsyncMock(
            return_value={
                "verifier_result": {
                    "verdict": "pass",
                    "reason": "Mostly okay",
                    "contradictions": ["Date does not match OCR text exactly"],
                }
            }
        )
        result = await node.run(state)
        assert result["pending_human_review"] is True
        assert "Contradictions" in result["history"][0]["escalation_reason"]

    @pytest.fixture
    def llm_client(self):
        """Mock LLM client."""
        client = MagicMock()
        client.invoke_agent = AsyncMock()
        return client

    @pytest.fixture
    def node(self, llm_client):
        """Review node instance with mocked dependencies."""
        return AgentReviewNode(llm_client)

    @pytest.mark.asyncio
    async def test_escalate_on_critical_issue(self, node):
        """Critical issues should always escalate to human review."""
        state = {
            "current_step": "completeness_check",
            "agent_1_result": {
                "confidence_score": 1.0,
                "issues": [{"severity": "critical", "description": "Missing discharge summary"}],
                "suggested_updates": [{"field": "doc", "suggested_value": "fix"}],
            },
        }
        result = await node.run(state)
        assert result["pending_human_review"] is True
        assert "Hard constraints failed" in result["history"][0]["escalation_reason"]

    @pytest.mark.asyncio
    async def test_escalate_on_large_amount(self, node):
        """Claims > 5M VND should always escalate."""
        state = {
            "current_step": "quality_check",
            "agent_2_result": {
                "confidence_score": 0.95,
                "evidence": {"total_claim_amount": 6_000_000},
                "issues": [{"severity": "low", "description": "Minor fix"}],
                "suggested_updates": [{"field": "icd", "suggested_value": "K29.7"}],
            },
        }
        result = await node.run(state)
        assert result["pending_human_review"] is True
        assert (
            f"Amount 6000000 >= {node.amount_threshold}"
            in result["history"][0]["escalation_reason"]
        )

    @pytest.mark.asyncio
    async def test_auto_approve_on_verifier_pass(self, node):
        """Reliable updates with high confidence and verifier pass should auto-approve."""
        state = {
            "current_step": "quality_check",
            "agent_2_result": {
                "confidence_score": 0.95,
                "evidence": {"total_claim_amount": 1_000_000},
                "issues": [{"severity": "low", "description": "Minor fix"}],
                "suggested_updates": [{"field": "icd", "suggested_value": "K29.7"}],
            },
        }

        # Mock the verifier agent call (which is part of the node during init)
        node.verifier_agent = AsyncMock(
            return_value={
                "verifier_result": {"verdict": "pass", "reason": "Everything looks grounded."}
            }
        )

        result = await node.run(state)
        assert "agent_2_result" in result
        assert result["agent_2_result"]["is_auto_reviewed"] is True
        assert result["history"][0]["auto_reviewed"] is True

    @pytest.mark.asyncio
    async def test_escalate_on_verifier_fail(self, node):
        """If the verifier finds an issue, it must escalate."""
        state = {
            "current_step": "quality_check",
            "agent_2_result": {
                "confidence_score": 0.95,
                "evidence": {"total_claim_amount": 1_000_000},
                "issues": [{"severity": "low", "description": "Minor fix"}],
                "suggested_updates": [{"field": "icd", "suggested_value": "K29.7"}],
            },
        }

        # Mock the verifier agent to fail
        node.verifier_agent = AsyncMock(
            return_value={
                "verifier_result": {"verdict": "fail", "reason": "Contradiction found in ICD code."}
            }
        )

        result = await node.run(state)
        # Assert escalation
        assert result["pending_human_review"] is True
        assert "Verifier risk" in result["history"][0]["escalation_reason"]
