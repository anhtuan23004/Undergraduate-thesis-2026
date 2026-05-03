"""Tests for routing functions in the multi-agent workflow.

These tests verify that the routing logic correctly handles
various agent results and human review decisions.
"""

from graphs.routing import (
    _get_decision_from_result,
    _get_human_decision,
    route_after_agent_review,
    route_after_completeness,
    route_after_completeness_review,
    route_after_final_review,
    route_after_quality,
    route_after_quality_review,
)


class TestGetDecisionFromResult:
    """Tests for _get_decision_from_result helper."""

    def test_accept_decision(self):
        """Should return 'accept' when valid=True."""
        result = {"valid": True}
        assert _get_decision_from_result(result) == "accept"

    def test_explicit_accept(self):
        """Should return 'accept' when decision field is 'accept'."""
        result = {"decision": "accept"}
        assert _get_decision_from_result(result) == "accept"

    def test_explicit_reject(self):
        """Should return 'reject' when decision field is 'reject'."""
        result = {"decision": "reject"}
        assert _get_decision_from_result(result) == "reject"

    def test_explicit_accept_with_edit(self):
        """Should return 'accept_with_edit' when decision field is 'accept_with_edit'."""
        result = {"decision": "accept_with_edit"}
        assert _get_decision_from_result(result) == "accept_with_edit"

    def test_reject_with_critical_issue(self):
        """Should return 'reject' when valid=False with critical issue."""
        result = {"valid": False, "issues": [{"severity": "critical", "code": "TEST"}]}
        assert _get_decision_from_result(result) == "reject"

    def test_reject_with_high_issue(self):
        """Should return 'reject' when valid=False with high issue."""
        result = {"valid": False, "issues": [{"severity": "high", "code": "TEST"}]}
        assert _get_decision_from_result(result) == "reject"

    def test_accept_with_edit_with_low_issue(self):
        """Should return 'accept_with_edit' when valid=False with only low issues."""
        result = {"valid": False, "issues": [{"severity": "low", "code": "TEST"}]}
        assert _get_decision_from_result(result) == "accept_with_edit"

    def test_accept_with_edit_with_medium_issue(self):
        """Should return 'accept_with_edit' when valid=False with only medium issues."""
        result = {"valid": False, "issues": [{"severity": "medium", "code": "TEST"}]}
        assert _get_decision_from_result(result) == "accept_with_edit"

    def test_reject_with_low_and_critical_issue(self):
        """Should return 'reject' when any issue is critical."""
        result = {
            "valid": False,
            "issues": [
                {"severity": "low", "code": "TEST1"},
                {"severity": "critical", "code": "TEST2"},
            ],
        }
        assert _get_decision_from_result(result) == "reject"

    def test_empty_result(self):
        """Should return 'reject' when result is empty/None."""
        assert _get_decision_from_result({}) == "reject"
        assert _get_decision_from_result(None) == "reject"


class TestGetHumanDecision:
    """Tests for _get_human_decision helper."""

    def test_approve(self):
        """Should return 'approve' when decision is 'approve'."""
        state = {"human_review_result": {"decision": "approve"}}
        assert _get_human_decision(state) == "approve"

    def test_reject(self):
        """Should return 'reject' when decision is 'reject'."""
        state = {"human_review_result": {"decision": "reject"}}
        assert _get_human_decision(state) == "reject"

    def test_edit(self):
        """Should return 'edit' when decision is 'edit'."""
        state = {"human_review_result": {"decision": "edit"}}
        assert _get_human_decision(state) == "edit"

    def test_no_human_review_result(self):
        """Should return 'reject' when human_review_result is missing."""
        state = {}
        assert _get_human_decision(state) == "reject"

    def test_empty_human_review_result(self):
        """Should return 'reject' when human_review_result is empty."""
        state = {"human_review_result": {}}
        assert _get_human_decision(state) == "reject"


class TestRouteAfterCompleteness:
    """Tests for route_after_completeness routing."""

    def test_accept_routes_to_quality(self):
        """Valid accept should route to quality_check."""
        state = {"agent_1_result": {"valid": True}}
        assert route_after_completeness(state) == "quality_check"

    def test_reject_routes_to_final(self):
        """Invalid reject should route to final_decision."""
        state = {"agent_1_result": {"valid": False, "issues": [{"severity": "high"}]}}
        assert route_after_completeness(state) == "final_decision"

    def test_accept_with_edit_routes_to_agent_review(self):
        """Soft issues should route to agent_review."""
        state = {"agent_1_result": {"valid": False, "issues": [{"severity": "low"}]}}
        assert route_after_completeness(state) == "agent_review"

    def test_edited_result_takes_precedence(self):
        """Edited result should override original agent result."""
        state = {
            "agent_1_result": {"valid": True},
            "edited_agent_1_result": {"decision": "accept_with_edit"},
        }
        assert route_after_completeness(state) == "agent_review"


class TestRouteAfterQuality:
    """Tests for route_after_quality routing."""

    def test_accept_routes_to_final(self):
        """Valid accept should route to final_decision."""
        state = {"agent_2_result": {"valid": True}}
        assert route_after_quality(state) == "final_decision"

    def test_reject_routes_to_final(self):
        """Invalid reject should route to final_decision."""
        state = {"agent_2_result": {"valid": False, "issues": [{"severity": "high"}]}}
        assert route_after_quality(state) == "final_decision"

    def test_accept_with_edit_routes_to_agent_review(self):
        """Soft issues should route to agent_review."""
        state = {"agent_2_result": {"valid": False, "issues": [{"severity": "low"}]}}
        assert route_after_quality(state) == "agent_review"

    def test_edited_result_takes_precedence(self):
        """Edited result should override original agent result."""
        state = {
            "agent_2_result": {"valid": True},
            "edited_agent_2_result": {"decision": "accept_with_edit"},
        }
        assert route_after_quality(state) == "agent_review"


class TestRouteAfterAgentReview:
    """Tests for route_after_agent_review routing."""

    def test_auto_reviewed_completeness_routes_to_quality(self):
        """Auto-reviewed completeness should route to quality_check."""
        state = {
            "current_step": "agent_reviewed_completeness",
            "agent_1_result": {"is_auto_reviewed": True},
        }
        assert route_after_agent_review(state) == "quality_check"

    def test_auto_reviewed_quality_routes_to_final(self):
        """Auto-reviewed quality should route to final_decision."""
        state = {
            "current_step": "agent_reviewed_quality",
            "agent_2_result": {"is_auto_reviewed": True},
        }
        assert route_after_agent_review(state) == "final_decision"

    def test_not_auto_reviewed_routes_to_human(self):
        """Not auto-reviewed should route to human_review."""
        state = {
            "current_step": "agent_review_escalated_quality",
            "agent_2_result": {"is_auto_reviewed": False},
        }
        assert route_after_agent_review(state) == "human_review"

    def test_missing_result_routes_to_human(self):
        """Missing agent result should route to human_review."""
        state = {"current_step": "agent_review_escalated_completeness"}
        assert route_after_agent_review(state) == "human_review"


class TestRouteAfterCompletenessReview:
    """Tests for route_after_completeness_review routing."""

    def test_approve_routes_to_quality(self):
        """Approve should route to quality_check."""
        state = {"human_review_result": {"decision": "approve"}}
        assert route_after_completeness_review(state) == "quality_check"

    def test_reject_routes_to_final(self):
        """Reject should route to final_decision."""
        state = {"human_review_result": {"decision": "reject"}}
        assert route_after_completeness_review(state) == "final_decision"

    def test_edit_routes_to_completeness(self):
        """Edit should route to completeness_check."""
        state = {"human_review_result": {"decision": "edit"}}
        assert route_after_completeness_review(state) == "completeness_check"


class TestRouteAfterQualityReview:
    """Tests for route_after_quality_review routing."""

    def test_approve_routes_to_final(self):
        """Approve should route to final_decision."""
        state = {"human_review_result": {"decision": "approve"}}
        assert route_after_quality_review(state) == "final_decision"

    def test_reject_routes_to_final(self):
        """Reject should route to final_decision."""
        state = {"human_review_result": {"decision": "reject"}}
        assert route_after_quality_review(state) == "final_decision"

    def test_edit_routes_to_quality(self):
        """Edit should route to quality_check."""
        state = {"human_review_result": {"decision": "edit"}}
        assert route_after_quality_review(state) == "quality_check"


class TestRouteAfterFinalReview:
    """Tests for route_after_final_review routing."""

    def test_approve_routes_to_human_review(self):
        """Approve from final agent should route to human_review for final sign-off."""
        state = {"final_result": {"decision": "approve"}}
        assert route_after_final_review(state) == "human_review"

    def test_reject_routes_to_human_review(self):
        """Reject from final agent should route to human_review for final sign-off."""
        state = {"final_result": {"decision": "reject"}}
        assert route_after_final_review(state) == "human_review"

    def test_edit_routes_to_quality(self):
        """Edit from final agent should still route to quality_check if agent wants more info."""
        state = {"final_result": {"decision": "edit"}}
        assert route_after_final_review(state) == "quality_check"

    def test_final_result_decision_takes_precedence(self):
        state = {
            "human_review_result": {"decision": "edit"},  # Previous human decision
            "final_result": {"decision": "approve"},  # Final agent decision
        }
        # DecisionAgent result should now route to human_review for final approval
        assert route_after_final_review(state) == "human_review"


class TestRouteAfterFinalHumanReview:
    """Tests for route_after_human_review specifically for final stage."""

    def test_final_approve_routes_to_end(self):
        """Human approval of the final decision should route to end."""
        state = {"human_review_result": {"decision": "approve", "stage": "final"}}
        from graphs.routing import route_after_human_review

        assert route_after_human_review(state) == "end"

    def test_final_reject_routes_to_end(self):
        """Human rejection of the final decision should route to end."""
        state = {"human_review_result": {"decision": "reject", "stage": "final"}}
        from graphs.routing import route_after_human_review

        assert route_after_human_review(state) == "end"

    def test_final_edit_routes_to_quality(self):
        """Human request for edit on final decision should route to quality_check."""
        state = {"human_review_result": {"decision": "edit", "stage": "final"}}
        from graphs.routing import route_after_human_review

        assert route_after_human_review(state) == "quality_check"
