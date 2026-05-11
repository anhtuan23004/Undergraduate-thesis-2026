"""Tests for agent audit helpers."""

from agents.audit import save_agent_audit_log


async def test_save_agent_audit_log_does_not_raise_on_database_error(monkeypatch):
    def raise_db_error(_name):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("agents.audit.get_collection", raise_db_error)

    await save_agent_audit_log(
        state={"run_id": "RUN-001", "claim_id": "CLAIM-001"},
        step_name="quality_agent",
        agent_name="QualityAgent",
        result={"decision": "accept"},
    )
