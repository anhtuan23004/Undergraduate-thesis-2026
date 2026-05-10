"""Audit logging helpers for agent node execution."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from mongodb_client import get_collection

logger = structlog.get_logger()


async def save_agent_audit_log(
    *,
    state: dict[str, Any],
    step_name: str,
    agent_name: str,
    result: dict[str, Any],
) -> None:
    """Persist an audit log entry without affecting workflow business state."""
    try:
        await asyncio.to_thread(
            _insert_audit_log,
            state=state,
            step_name=step_name,
            agent_name=agent_name,
            result=result,
        )
    except Exception as exc:
        logger.warning("Failed to save audit log", error=str(exc))


def _insert_audit_log(
    *,
    state: dict[str, Any],
    step_name: str,
    agent_name: str,
    result: dict[str, Any],
) -> None:
    audit_col = get_collection("audit_logs")
    audit_col.insert_one(
        {
            "run_id": state.get("run_id"),
            "claim_id": state.get("claim_id"),
            "step_name": step_name,
            "agent_name": agent_name,
            "result_json": result,
            "timestamp": datetime.now(UTC),
        }
    )
