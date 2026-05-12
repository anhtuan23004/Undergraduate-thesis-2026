"""Tests for Langfuse session propagation helpers."""

from agent import _build_agent_config, _langfuse_session_id


def test_langfuse_session_id_uses_workflow_run_id() -> None:
    assert _langfuse_session_id({"run_id": "run-123"}) == "run-123"


def test_langfuse_session_id_prefers_explicit_session_id() -> None:
    assert _langfuse_session_id({"session_id": "session-123", "run_id": "run-123"}) == "session-123"


def test_langfuse_session_id_rejects_invalid_values() -> None:
    assert _langfuse_session_id({"run_id": "phiên-1"}) is None
    assert _langfuse_session_id({"run_id": ""}) is None


def test_agent_config_keeps_workflow_metadata_for_langfuse_filtering() -> None:
    config = _build_agent_config(
        "CompletenessAgent_claim-1",
        {"run_id": "run-1", "claim_id": "claim-1", "agent_role": "completeness"},
        [],
    )

    assert config["run_name"] == "CompletenessAgent_claim-1"
    assert config["metadata"]["trace_name"] == "CompletenessAgent_claim-1"
    assert config["metadata"]["run_id"] == "run-1"
    assert config["metadata"]["claim_id"] == "claim-1"
    assert config["metadata"]["agent_role"] == "completeness"
