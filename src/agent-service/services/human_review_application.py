"""Application use case for applying human review decisions."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from config import settings
from schemas.agent_outputs import HumanReviewResult
from workflow.contracts import STAGE_FINAL
from workflow.policy import (
    STAGE_POLICIES,
    StagePolicy,
    review_stage_from_state,
    stage_policy,
)

from services.graph_service import get_graph
from services.workflow_state import build_workflow_response, extract_pause_state


@dataclass(frozen=True)
class HumanReviewCommand:
    """Human review decision payload independent from transport schemas."""

    decision: str
    notes: str | None = None
    edited_result: dict | None = None


class WorkflowRunNotFound(Exception):
    """Raised when a workflow checkpoint cannot be found."""

    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.run_id = run_id


class HumanReviewTimeout(Exception):
    """Raised when applying a human review exceeds the configured timeout."""

    def __init__(self, timeout_seconds: int | float) -> None:
        super().__init__(timeout_seconds)
        self.timeout_seconds = timeout_seconds


class HumanReviewApplication:
    """Apply human review to a persisted workflow graph run."""

    def __init__(
        self,
        graph_provider: Callable[[], Awaitable[Any]] = get_graph,
        timeout_seconds: int | float = settings.PROCESS_TIMEOUT,
    ) -> None:
        self._graph_provider = graph_provider
        self._timeout_seconds = timeout_seconds

    async def apply(self, run_id: str, command: HumanReviewCommand) -> dict:
        """Apply a human decision and continue the workflow graph."""
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._apply(run_id, command)
        except TimeoutError as exc:
            raise HumanReviewTimeout(self._timeout_seconds) from exc

    async def _apply(self, run_id: str, command: HumanReviewCommand) -> dict:
        graph = await self._graph_provider()
        config = {"configurable": {"thread_id": run_id}}

        current_state = await graph.aget_state(config)
        if not current_state or not current_state.values:
            raise WorkflowRunNotFound(run_id)

        stage = review_stage_from_state(current_state.values)
        state_update = build_human_review_update(stage, command)

        await graph.aupdate_state(config, state_update, as_node="human_review")
        result = await graph.ainvoke(None, config=config)

        snapshot = await graph.aget_state(config)
        is_pending, is_paused, pause_at = extract_pause_state(snapshot)
        return build_workflow_response(result, is_pending, is_paused, pause_at)


def build_human_review_update(stage: str, command: HumanReviewCommand) -> dict[str, Any]:
    """Build graph state update for a human review decision."""
    human_review_result = HumanReviewResult.model_validate(
        {
            "decision": command.decision,
            "notes": command.notes,
            "stage": stage,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
    ).model_dump()

    state_update: dict[str, Any] = {
        "human_review_result": human_review_result,
        "current_step": "human_review_complete",
        "history": [
            {
                "step": "human_review",
                "decision": command.decision,
                "notes": command.notes,
                "resumed": True,
            }
        ],
    }

    edited_key = edited_result_key_after_human_review(stage, command)
    if edited_key:
        state_update[edited_key] = command.edited_result

    if stage == STAGE_FINAL and command.decision == "reject":
        rejection_reason = command.notes or "Thẩm định viên từ chối kết luận cuối cùng."
        state_update["final_result"] = {
            "decision": "reject",
            "approved_amount": 0,
            "rejection_reason": rejection_reason,
            "issues_summary": [],
            "message": f"Kết luận cuối cùng bị thẩm định viên từ chối: {rejection_reason}",
        }

    return state_update


def edited_result_key_after_human_review(
    stage: str,
    command: HumanReviewCommand,
) -> str | None:
    """Return the graph state key that should receive a human-edited result."""
    if command.decision != "edit" or not command.edited_result:
        return None

    policy = stage_policy(stage)
    if policy.edited_result_key:
        return policy.edited_result_key

    next_policy = _policy_for_node(policy.next_after_human_edit)
    if next_policy:
        return next_policy.edited_result_key
    return None


def _policy_for_node(node: str) -> StagePolicy | None:
    return next((policy for policy in STAGE_POLICIES.values() if policy.node == node), None)
