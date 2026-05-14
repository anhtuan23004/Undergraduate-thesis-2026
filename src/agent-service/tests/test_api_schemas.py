"""Contract tests for API schemas and shared model types.

These tests verify that Pydantic models accept valid data, reject invalid
data, and that typed constants stay consistent across modules.
"""

import pytest
from api.errors import workflow_error
from api.schemas import HumanReviewRequest, WorkflowErrorResponse
from pydantic import ValidationError
from schemas.agent_outputs import (
    FinalDecisionOutput,
    HumanReviewResult,
    Issue,
)
from workflow.contracts import (
    SEVERITY_ESCALATION,
    SEVERITY_ORDER,
    SEVERITY_REVIEW_REQUIRED,
)

# ---------------------------------------------------------------------------
# HumanReviewRequest
# ---------------------------------------------------------------------------


class TestHumanReviewRequest:
    """Tests for HumanReviewRequest API schema."""

    @pytest.mark.parametrize("decision", ["approve", "reject", "edit"])
    def test_valid_decisions_accepted(self, decision: str) -> None:
        req = HumanReviewRequest(decision=decision)
        assert req.decision == decision

    def test_invalid_decision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HumanReviewRequest(decision="maybe")

    def test_notes_and_edited_result_optional(self) -> None:
        req = HumanReviewRequest(decision="approve")
        assert req.notes is None
        assert req.edited_result is None


# ---------------------------------------------------------------------------
# HumanReviewResult (graph state model)
# ---------------------------------------------------------------------------


class TestHumanReviewResult:
    """Tests for HumanReviewResult typed model."""

    def test_valid_approve(self) -> None:
        result = HumanReviewResult(decision="approve", stage="completeness")
        assert result.decision == "approve"
        assert result.stage == "completeness"

    def test_invalid_decision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HumanReviewResult(decision="pending")

    def test_optional_fields_default_none(self) -> None:
        result = HumanReviewResult(decision="reject")
        assert result.notes is None
        assert result.stage is None
        assert result.reviewed_at is None


# ---------------------------------------------------------------------------
# FinalDecisionOutput — contract: no "edit" decision
# ---------------------------------------------------------------------------


class TestFinalDecisionContract:
    """Tests for FinalDecisionOutput decision values."""

    @pytest.mark.parametrize("decision", ["approve", "reject"])
    def test_valid_decisions_accepted(self, decision: str) -> None:
        output = FinalDecisionOutput(
            decision=decision,
            message="Test message",
        )
        assert output.decision == decision

    def test_edit_decision_rejected(self) -> None:
        """FinalDecisionOutput must NOT accept 'edit' — this is a dead branch."""
        with pytest.raises(ValidationError):
            FinalDecisionOutput(decision="edit", message="Test")


# ---------------------------------------------------------------------------
# Issue and IssueSummary — severity enum consistency
# ---------------------------------------------------------------------------


class TestSeverityConsistency:
    """Tests that severity values used across schemas and constants are consistent."""

    @pytest.mark.parametrize("severity", ["critical", "high", "medium", "low"])
    def test_issue_accepts_all_severity_levels(self, severity: str) -> None:
        issue = Issue(
            severity=severity,
            code="TEST",
            description="test",
        )
        assert issue.severity == severity

    def test_issue_rejects_invalid_severity(self) -> None:
        with pytest.raises(ValidationError):
            Issue(severity="extreme", code="TEST", description="test")

    def test_severity_order_matches_escalation_sets(self) -> None:
        """SEVERITY_ESCALATION and SEVERITY_REVIEW_REQUIRED must be subsets of SEVERITY_ORDER."""
        assert SEVERITY_ESCALATION.issubset(set(SEVERITY_ORDER))
        assert SEVERITY_REVIEW_REQUIRED.issubset(set(SEVERITY_ORDER))

    def test_escalation_is_subset_of_review_required(self) -> None:
        """Escalation (reject) must be stricter than review-required (agent review)."""
        assert SEVERITY_ESCALATION.issubset(SEVERITY_REVIEW_REQUIRED)


# ---------------------------------------------------------------------------
# WorkflowErrorResponse
# ---------------------------------------------------------------------------


class TestWorkflowErrorResponse:
    """Tests for WorkflowErrorResponse schema."""

    def test_minimal_error(self) -> None:
        resp = WorkflowErrorResponse(error="Not found", status_code=404)
        assert resp.error == "Not found"
        assert resp.status_code == 404
        assert resp.error_detail is None
        assert resp.endpoint is None

    def test_full_error(self) -> None:
        resp = WorkflowErrorResponse(
            error="Timeout",
            error_detail="Process exceeded 300s",
            status_code=504,
            endpoint="/workflows/run",
        )
        assert resp.endpoint == "/workflows/run"

    def test_workflow_error_helper_uses_standard_shape(self) -> None:
        exc = workflow_error(
            504,
            "Timeout",
            error_detail="Process exceeded 300s",
            endpoint="/workflows/resume",
        )

        assert exc.status_code == 504
        assert WorkflowErrorResponse.model_validate(exc.detail)
        assert exc.detail == {
            "error": "Timeout",
            "error_detail": "Process exceeded 300s",
            "status_code": 504,
            "endpoint": "/workflows/resume",
        }
