"""Tests for workflow state helper functions."""

from types import SimpleNamespace

from services.workflow_state import (
    build_initial_state,
    build_workflow_response,
    determine_review_stage,
    extract_pause_state,
)


def test_build_initial_state_sets_required_defaults():
    """Initial graph state should contain all required workflow keys."""
    state = build_initial_state(
        run_id="run-1",
        claim_id="claim-1",
        policy_number="policy-1",
        input_file="/tmp/doc.pdf",
        extracted_documents={"ocr_stage": "phase1_classified", "documents": []},
        file_hash="hash-1",
    )

    assert state["run_id"] == "run-1"
    assert state["claim_id"] == "claim-1"
    assert state["policy_number"] == "policy-1"
    assert state["input_file"] == "/tmp/doc.pdf"
    assert state["file_hash"] == "hash-1"
    assert state["extracted_documents"] == {"ocr_stage": "phase1_classified", "documents": []}
    assert state["agent_1_result"] is None
    assert state["agent_2_result"] is None
    assert state["final_result"] is None
    assert state["history"] == []
    assert state["current_step"] == "start"
    assert state["active_stage"] == "completeness"
    assert state["review_stage"] == "none"
    assert state["workflow_status"] == "running"
    assert state["ocr_stage"] == "phase1_classified"
    assert state["should_continue"] is True
    assert state["pending_human_review"] is False


def test_build_workflow_response_preserves_run_response_shape_by_default():
    """Default response shape should match existing run/resume/continue API payloads."""
    response = build_workflow_response(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "policy_number": "policy-1",
            "extracted_documents": {"documents": []},
            "agent_1_result": {"valid": True},
            "agent_2_result": None,
            "human_review_result": {"decision": "approve"},
            "final_result": None,
            "current_step": "quality_check",
            "active_stage": "quality",
            "review_stage": "none",
            "workflow_status": "paused",
            "history": [{"step": "completeness_agent"}],
            "error": None,
        },
        is_pending=False,
        is_paused=True,
        pause_at="quality_check",
    )

    assert response == {
        "run_id": "run-1",
        "claim_id": "claim-1",
        "policy_number": "policy-1",
        "extracted_documents": {"documents": []},
        "final_result": None,
        "agent_1_result": {"valid": True},
        "agent_2_result": None,
        "current_step": "quality_check",
        "active_stage": "quality",
        "review_stage": "none",
        "workflow_status": "paused",
        "pending_human_review": False,
        "paused": True,
        "pause_at": "quality_check",
        "history": [{"step": "completeness_agent"}],
        "error": None,
    }


def test_build_workflow_response_can_include_human_review_for_status():
    """Status endpoint should keep exposing human review result."""
    response = build_workflow_response(
        {"human_review_result": {"decision": "approve"}},
        is_pending=False,
        is_paused=False,
        pause_at=None,
        include_human_review=True,
    )

    assert response["human_review_result"] == {"decision": "approve"}


def test_extract_pause_state_identifies_human_review_pause():
    """Human review in next nodes should set pending_human_review."""
    snapshot = SimpleNamespace(next=("human_review",))

    assert extract_pause_state(snapshot) == (True, True, "human_review")


def test_extract_pause_state_tolerates_missing_snapshot():
    """Missing graph snapshots should be represented as not paused."""
    assert extract_pause_state(None) == (False, False, None)


def test_extract_pause_state_identifies_non_human_pause():
    """Any non-empty next node should be represented as a normal pause."""
    snapshot = SimpleNamespace(next=("quality_check",))

    assert extract_pause_state(snapshot) == (False, True, "quality_check")


def test_determine_review_stage_delegates_to_policy_fallbacks():
    """Legacy wrapper uses the workflow policy stage inference."""
    assert determine_review_stage({"final_result": {"decision": "approve"}}) == "final"
    assert determine_review_stage({"current_step": "agent_reviewed_completeness"}) == "completeness"
    assert determine_review_stage({"agent_1_result": {"valid": True}}) == "quality"


def test_determine_review_stage_prefers_explicit_review_stage():
    assert (
        determine_review_stage({"review_stage": "quality", "final_result": {"decision": "approve"}})
        == "quality"
    )
