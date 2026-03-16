"""Unit tests for HITL decision engine."""

from interfaces.api.models import ResumeDecision
from interfaces.api.routes import HITLDecisionEngine


class TestHITLDecisionEngine:
    """Validate interrupt and resume decision contract."""

    def test_build_interrupts_maps_stages(self):
        """Build interrupt payloads with correct stage/action mapping."""
        interrupts = HITLDecisionEngine.build_interrupts(
            run_id="run_1",
            review_nodes=["completeness_review", "quality_review", "final_review"],
            state_values={"claim_id": "CLM-001", "policy_number": "POL-001"},
            created_at="2026-01-01T00:00:00Z",
        )

        assert len(interrupts) == 3
        stages = [item.stage for item in interrupts]
        actions = [item.action for item in interrupts]
        assert stages == ["completeness", "quality", "final"]
        assert actions == ["review_completeness", "review_quality", "review_final_decision"]

    def test_validate_and_select_decision_by_active_stage(self):
        """Select decision by active review stage and enforce interrupt_id contract."""
        pending_review = {
            "review_node": "quality_review",
            "interrupts": [
                {
                    "interrupt_id": "intr_completeness",
                    "stage": "completeness",
                    "allowed_decisions": ["approve", "reject", "edit"],
                },
                {
                    "interrupt_id": "intr_quality",
                    "stage": "quality",
                    "allowed_decisions": ["approve", "reject", "edit"],
                },
            ],
        }
        decisions = [
            ResumeDecision(interrupt_id="intr_completeness", decision="approve"),
            ResumeDecision(interrupt_id="intr_quality", decision="reject"),
        ]

        active_interrupt, active_decision = HITLDecisionEngine.validate_and_select_decision(
            pending_review=pending_review,
            decisions=decisions,
        )

        assert active_interrupt["interrupt_id"] == "intr_quality"
        assert active_decision.decision == "reject"

    def test_apply_edit_decision_updates_quality_payload(self):
        """Map edit decision to state update payload for quality review."""
        state_update = HITLDecisionEngine.apply_decision_to_state(
            interrupt_id="intr_quality",
            decision="edit",
            reviewed_by="reviewer",
            comment="Fix value",
            review_node="quality_review",
            edited_payload={"valid": True, "issues": []},
        )

        assert state_update["human_review_result"]["decision"] == "edit"
        assert state_update["human_review_result"]["interrupt_id"] == "intr_quality"
        assert state_update["edited_agent_2_result"] == {"valid": True, "issues": []}
        assert isinstance(state_update["history"], list)
