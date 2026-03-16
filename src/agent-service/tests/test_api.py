"""Integration tests for v2 run-based API endpoints."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_storage():
    """Create a mock Redis storage."""
    storage = MagicMock()
    storage.get_thread_by_claim = AsyncMock(return_value=None)
    storage.set_claim_thread_mapping = AsyncMock(return_value=True)
    storage.delete_claim_thread_mapping = AsyncMock(return_value=True)
    storage.get_pending_review = AsyncMock(return_value=None)
    storage.get_error = AsyncMock(return_value=None)
    storage.set_pending_review = AsyncMock(return_value=True)
    storage.delete_pending_review = AsyncMock(return_value=True)
    storage.get_all_pending_reviews = AsyncMock(return_value={})
    return storage


@pytest.fixture
def mock_graph():
    """Create a mock LangGraph."""
    graph = MagicMock()

    mock_state = MagicMock()
    mock_state.values = {
        "run_id": "run_123",
        "claim_id": "CLM-001",
        "policy_number": "POL-001",
        "agent_1_result": {"valid": True, "issues": []},
        "agent_2_result": {"valid": True, "issues": []},
        "human_review_result": None,
        "final_result": {"decision": "APPROVE"},
        "pending_human_review": False,
        "error": None,
        "current_step": "final_decision_complete",
    }
    mock_state.next = ()

    graph.aget_state = AsyncMock(return_value=mock_state)
    graph.aupdate_state = AsyncMock(return_value=None)

    async def _empty_astream(*args, **kwargs):
        if False:
            yield None

    graph.astream = _empty_astream
    return graph


@pytest.fixture
def client(mock_storage, mock_graph):
    """Create test client with mocked dependencies."""
    with patch("interfaces.api.routes._graph", mock_graph), patch(
        "interfaces.api.routes.get_storage", return_value=mock_storage
    ):
        from interfaces.api.routes import router

        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as test_client:
            yield test_client


class TestCreateRunEndpoint:
    """Test run creation endpoint."""

    def test_create_run_invalid_body(self, client):
        """Test creation with invalid request body."""
        response = client.post("/runs", json={"claim_id": "CLM-001"})
        assert response.status_code == 422

    def test_create_run_valid_data(self, client, mock_storage):
        """Test creation with valid request body."""
        uploads_dir = "/tmp/agent-service/uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        test_file = os.path.join(uploads_dir, "test-claim.pdf")
        with open(test_file, "wb") as f:
            f.write(b"dummy pdf content")

        response = client.post(
            "/runs",
            json={
                "claim_id": "CLM-001",
                "policy_number": "POL-001",
                "input_file": "test-claim.pdf",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"].startswith("run_")
        assert data["status"] == "created"
        mock_storage.set_claim_thread_mapping.assert_called_once()


class TestRunStatusEndpoint:
    """Test run status endpoint."""

    def test_status_not_found(self, client, mock_storage):
        """Test status returns 404 for unknown run."""
        mock_storage.get_thread_by_claim = AsyncMock(return_value=None)
        mock_storage.get_pending_review = AsyncMock(return_value=None)

        response = client.get("/runs/run_unknown")
        assert response.status_code == 404

    def test_status_running(self, client, mock_storage, mock_graph):
        """Test status returns running for in-progress run."""
        mock_storage.get_thread_by_claim = AsyncMock(return_value="run_123")
        mock_storage.get_error = AsyncMock(return_value=None)
        mock_storage.get_pending_review = AsyncMock(return_value=None)

        mock_state = MagicMock()
        mock_state.values = {"run_id": "run_123", "claim_id": "CLM-001", "current_step": "quality_check"}
        mock_state.next = ("quality_check",)
        mock_graph.aget_state = AsyncMock(return_value=mock_state)

        response = client.get("/runs/run_123")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["final_output"] is None

    def test_status_interrupted(self, client, mock_storage, mock_graph):
        """Test status returns interrupted when review is pending."""
        mock_storage.get_thread_by_claim = AsyncMock(return_value="run_456")
        mock_storage.get_error = AsyncMock(return_value=None)
        mock_storage.get_pending_review = AsyncMock(
            return_value={
                "run_id": "run_456",
                "thread_id": "run_456",
                "review_node": "quality_review",
                "interrupts": [
                    {
                        "interrupt_id": "intr_1",
                        "run_id": "run_456",
                        "stage": "quality",
                        "action": "review_quality",
                        "payload": {},
                        "allowed_decisions": ["approve", "reject", "edit"],
                        "created_at": "2026-01-01T00:00:00",
                    }
                ],
            }
        )

        mock_state = MagicMock()
        mock_state.values = {"run_id": "run_456", "claim_id": "CLM-002", "current_step": "quality_review"}
        mock_state.next = ("quality_review",)
        mock_graph.aget_state = AsyncMock(return_value=mock_state)

        response = client.get("/runs/run_456")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "interrupted"
        assert len(data["interrupts"]) == 1


class TestResumeRunEndpoint:
    """Test run resume endpoint."""

    def test_resume_not_found(self, client, mock_storage):
        """Test resume returns 404 if run is not interrupted."""
        mock_storage.get_pending_review = AsyncMock(return_value=None)

        response = client.post(
            "/runs/run_unknown/resume",
            json={
                "decisions": [{"interrupt_id": "intr_1", "decision": "approve"}],
                "reviewed_by": "tester",
            },
        )

        assert response.status_code == 404

    def test_resume_success(self, client, mock_storage, mock_graph):
        """Test resume accepts decision and schedules continuation."""
        mock_storage.get_pending_review = AsyncMock(
            return_value={
                "run_id": "run_123",
                "thread_id": "run_123",
                "review_node": "quality_review",
                "interrupts": [
                    {
                        "interrupt_id": "intr_1",
                        "run_id": "run_123",
                        "stage": "quality",
                        "action": "review_quality",
                        "payload": {},
                        "allowed_decisions": ["approve", "reject", "edit"],
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        )

        response = client.post(
            "/runs/run_123/resume",
            json={
                "decisions": [{"interrupt_id": "intr_1", "decision": "approve", "comment": "ok"}],
                "reviewed_by": "tester",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_123"
        assert data["status"] == "running"
        mock_graph.aupdate_state.assert_called_once()
        assert mock_storage.delete_pending_review.call_count >= 1
        mock_storage.delete_pending_review.assert_any_call("run_123")

    def test_resume_unknown_interrupt_returns_400(self, client, mock_storage):
        """Reject decisions that target unknown interrupt IDs."""
        mock_storage.get_pending_review = AsyncMock(
            return_value={
                "run_id": "run_123",
                "thread_id": "run_123",
                "review_node": "quality_review",
                "interrupts": [
                    {
                        "interrupt_id": "intr_known",
                        "run_id": "run_123",
                        "stage": "quality",
                        "action": "review_quality",
                        "payload": {},
                        "allowed_decisions": ["approve", "reject", "edit"],
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        )

        response = client.post(
            "/runs/run_123/resume",
            json={
                "decisions": [{"interrupt_id": "intr_other", "decision": "approve"}],
                "reviewed_by": "tester",
            },
        )
        assert response.status_code == 400

    def test_resume_edit_without_payload_returns_400(self, client, mock_storage):
        """Reject edit decisions without edited payload."""
        mock_storage.get_pending_review = AsyncMock(
            return_value={
                "run_id": "run_123",
                "thread_id": "run_123",
                "review_node": "quality_review",
                "interrupts": [
                    {
                        "interrupt_id": "intr_1",
                        "run_id": "run_123",
                        "stage": "quality",
                        "action": "review_quality",
                        "payload": {},
                        "allowed_decisions": ["approve", "reject", "edit"],
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        )

        response = client.post(
            "/runs/run_123/resume",
            json={
                "decisions": [{"interrupt_id": "intr_1", "decision": "edit"}],
                "reviewed_by": "tester",
            },
        )
        assert response.status_code == 400
