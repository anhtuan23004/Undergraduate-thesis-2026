"""Tests for the AgentReviewNode logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from graphs.agent_review import (
    REASON_HARD_CONSTRAINTS_FAILED,
    REASON_VERIFIER_CONTRADICTIONS,
    REASON_VERIFIER_FAILED,
    AgentReviewNode,
)


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
        assert result["review_stage"] == "completeness"
        assert result["workflow_status"] == "waiting_human"
        assert result["history"][0]["escalation_reason_code"] == REASON_HARD_CONSTRAINTS_FAILED
        assert "Trung bình" in result["history"][0]["escalation_reason"]

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
        assert result["history"][0]["escalation_reason_code"] == REASON_VERIFIER_CONTRADICTIONS
        assert "Date does not match OCR text exactly" in result["history"][0]["escalation_reason"]

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

    def test_parse_claim_amount_accepts_numeric_values(self, node):
        """Numeric OCR amounts should not raise while normalizing."""
        assert node._parse_claim_amount(1_000_000) == 1_000_000.0
        assert node._parse_claim_amount(1_000_000.5) == 1_000_000.5

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
        assert result["history"][0]["escalation_reason_code"] == REASON_HARD_CONSTRAINTS_FAILED

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
        assert result["history"][0]["escalation_reason_code"] == REASON_HARD_CONSTRAINTS_FAILED
        assert "Nên để human review" in result["history"][0]["escalation_reason"]
        assert "6,000,000" in result["history"][0]["escalation_reason"]

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
        assert result["review_stage"] == "none"
        assert result["workflow_status"] == "running"
        assert result["history"][0]["auto_reviewed"] is True

    @pytest.mark.asyncio
    async def test_explicit_review_stage_selects_completeness_result(self, node):
        state = {
            "review_stage": "completeness",
            "current_step": "quality_check",
            "agent_1_result": {
                "confidence_score": 0.95,
                "evidence": {"total_claim_amount": 1_000_000},
                "issues": [{"severity": "low", "description": "Minor fix"}],
                "suggested_updates": [{"field": "doc", "suggested_value": "fix"}],
            },
            "agent_2_result": {
                "confidence_score": 0.0,
                "issues": [{"severity": "critical", "description": "Wrong target"}],
            },
        }
        node.verifier_agent = AsyncMock(
            return_value={
                "verifier_result": {"verdict": "pass", "reason": "Everything looks grounded."}
            }
        )

        result = await node.run(state)

        assert "agent_1_result" in result
        assert result["agent_1_result"]["is_auto_reviewed"] is True

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
        assert result["history"][0]["escalation_reason_code"] == REASON_VERIFIER_FAILED
        assert "Contradiction found in ICD code." in result["history"][0]["escalation_reason"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("amount", [6_000_000, "6,000,000", "6.000.000", "invalid"])
    async def test_escalate_on_large_or_unparseable_amount_formats(self, node, amount):
        """OCR amount formats above threshold, or invalid values, must escalate."""
        state = {
            "current_step": "quality_check",
            "agent_2_result": {
                "confidence_score": 0.95,
                "evidence": {"total_claim_amount": amount},
                "issues": [{"severity": "low", "description": "Minor fix"}],
                "suggested_updates": [{"field": "icd", "suggested_value": "K29.7"}],
            },
        }

        result = await node.run(state)

        assert result["pending_human_review"] is True
        assert result["history"][0]["escalation_reason_code"] == REASON_HARD_CONSTRAINTS_FAILED
