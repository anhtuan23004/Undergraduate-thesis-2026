"""Tests for applying human review decisions outside the FastAPI route."""

from types import SimpleNamespace

import pytest
from api.schemas import HumanReviewRequest
from api.workflows import resume_workflow
from fastapi import HTTPException
from services.human_review_application import (
    HumanReviewApplication,
    HumanReviewCommand,
    HumanReviewTimeout,
    WorkflowRunNotFound,
)


class FakeGraph:
    def __init__(
        self,
        state: dict | None,
        *,
        result: dict | None = None,
        next_nodes: tuple[str, ...] = (),
    ) -> None:
        self.state = state
        self.result = result
        self.next_nodes = next_nodes
        self.updates = []
        self.invocations = []

    async def aget_state(self, config):
        return SimpleNamespace(values=self.state, next=self.next_nodes) if self.state else None

    async def aupdate_state(self, config, state_update, as_node=None):
        self.updates.append({"config": config, "state_update": state_update, "as_node": as_node})
        self.state = {**self.state, **state_update}

    async def ainvoke(self, value, config=None):
        self.invocations.append({"value": value, "config": config})
        return self.result or self.state


async def _provide(graph):
    return graph


@pytest.mark.asyncio
async def test_apply_edit_wires_completeness_result_key():
    graph = FakeGraph(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "review_stage": "completeness",
            "extracted_documents": {},
        },
        result={"run_id": "run-1", "claim_id": "claim-1", "workflow_status": "running"},
    )
    app = HumanReviewApplication(lambda: _provide(graph), timeout_seconds=5)

    await app.apply(
        "run-1",
        HumanReviewCommand(
            decision="edit",
            notes="fix completeness",
            edited_result={"decision": "accept"},
        ),
    )

    update = graph.updates[0]["state_update"]
    assert graph.updates[0]["as_node"] == "human_review"
    assert update["human_review_result"]["stage"] == "completeness"
    assert update["edited_agent_1_result"] == {"decision": "accept"}
    assert "edited_agent_2_result" not in update
    assert graph.invocations[0]["value"] is None


@pytest.mark.asyncio
async def test_apply_edit_wires_quality_result_key():
    graph = FakeGraph(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "review_stage": "quality",
            "extracted_documents": {},
        }
    )
    app = HumanReviewApplication(lambda: _provide(graph), timeout_seconds=5)

    await app.apply(
        "run-1",
        HumanReviewCommand(
            decision="edit",
            notes=None,
            edited_result={"decision": "accept_with_edit"},
        ),
    )

    update = graph.updates[0]["state_update"]
    assert update["human_review_result"]["stage"] == "quality"
    assert update["edited_agent_2_result"] == {"decision": "accept_with_edit"}
    assert "edited_agent_1_result" not in update


@pytest.mark.asyncio
async def test_apply_final_edit_targets_quality_result_key_via_policy():
    graph = FakeGraph(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "review_stage": "final",
            "final_result": {"decision": "reject"},
            "extracted_documents": {},
        }
    )
    app = HumanReviewApplication(lambda: _provide(graph), timeout_seconds=5)

    await app.apply(
        "run-1",
        HumanReviewCommand(
            decision="edit",
            notes="recheck quality",
            edited_result={"decision": "accept_with_edit"},
        ),
    )

    update = graph.updates[0]["state_update"]
    assert update["human_review_result"]["stage"] == "final"
    assert update["edited_agent_2_result"] == {"decision": "accept_with_edit"}
    assert "edited_agent_1_result" not in update


@pytest.mark.asyncio
async def test_apply_approve_does_not_write_edited_result_key():
    graph = FakeGraph(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "review_stage": "quality",
            "extracted_documents": {},
        }
    )
    app = HumanReviewApplication(lambda: _provide(graph), timeout_seconds=5)

    await app.apply("run-1", HumanReviewCommand(decision="approve", notes="ok"))

    update = graph.updates[0]["state_update"]
    assert update["human_review_result"]["decision"] == "approve"
    assert "edited_agent_1_result" not in update
    assert "edited_agent_2_result" not in update


@pytest.mark.asyncio
async def test_apply_missing_run_raises_not_found():
    app = HumanReviewApplication(lambda: _provide(FakeGraph(None)), timeout_seconds=5)

    with pytest.raises(WorkflowRunNotFound):
        await app.apply("missing-run", HumanReviewCommand(decision="approve"))


@pytest.mark.asyncio
async def test_resume_workflow_maps_missing_run_to_standard_404(monkeypatch):
    class MissingRunApplication:
        async def apply(self, run_id, command):
            raise WorkflowRunNotFound(run_id)

    monkeypatch.setattr("api.workflows.HumanReviewApplication", lambda: MissingRunApplication())

    with pytest.raises(HTTPException) as exc_info:
        await resume_workflow("missing-run", HumanReviewRequest(decision="approve"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["endpoint"] == "/workflows/resume"


@pytest.mark.asyncio
async def test_resume_workflow_maps_timeout_to_standard_504(monkeypatch):
    class TimeoutApplication:
        async def apply(self, run_id, command):
            raise HumanReviewTimeout(30)

    monkeypatch.setattr("api.workflows.HumanReviewApplication", lambda: TimeoutApplication())

    with pytest.raises(HTTPException) as exc_info:
        await resume_workflow("run-1", HumanReviewRequest(decision="approve"))

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail["endpoint"] == "/workflows/resume"
