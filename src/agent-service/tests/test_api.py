"""Integration tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock


# Mock the dependencies before importing the app
@pytest.fixture
def mock_storage():
    """Create a mock Redis storage."""
    storage = MagicMock()
    storage.get_claim_thread_mapping = AsyncMock(return_value=None)
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
    
    # Mock state
    mock_state = MagicMock()
    mock_state.values = {
        "claim_id": "test-123",
        "policy_number": "POL-001",
        "agent_1_result": {"valid": True, "issues": []},
        "agent_2_result": {"valid": True, "issues": []},
        "human_review_result": None,
        "final_result": None,
        "pending_human_review": False,
        "error": None,
    }
    mock_state.next = ()  # Empty tuple means finished
    
    graph.aget_state = AsyncMock(return_value=mock_state)
    graph.astream = AsyncMock(return_value=iter([]))
    
    return graph


@pytest.fixture
def client(mock_storage, mock_graph):
    """Create test client with mocked dependencies."""
    with patch("interfaces.api.routes._storage", mock_storage), \
         patch("interfaces.api.routes._graph", mock_graph), \
         patch("interfaces.api.routes.get_storage", return_value=mock_storage):
        from interfaces.api.routes import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        
        with TestClient(app) as test_client:
            yield test_client


class TestProcessClaimEndpoint:
    """Test claim processing endpoint."""
    
    def test_process_claim_invalid_body(self, client):
        """Test processing with invalid request body."""
        # Missing required fields
        response = client.post(
            "/multi-agent/process",
            json={"claim_id": "test-123"}
        )
        
        # Should return validation error (422)
        assert response.status_code == 422
        
    def test_process_claim_with_valid_data(self, client, mock_storage, mock_graph):
        """Test processing with valid request body."""
        response = client.post(
            "/multi-agent/process",
            json={
                "claim_id": "test-123",
                "policy_number": "POL-001",
                "input_file": {"type": "url", "url": "https://example.com/doc.pdf"}
            }
        )
        
        # Should return 200 (or 202 for async processing)
        assert response.status_code in [200, 202]
        
        # Verify storage was called
        mock_storage.set_claim_thread_mapping.assert_called_once()


class TestClaimStatusEndpoint:
    """Test claim status endpoint."""
    
    def test_status_not_found(self, client, mock_storage):
        """Test status returns 404 for unknown claim."""
        mock_storage.get_thread_by_claim = AsyncMock(return_value=None)
        mock_storage.get_pending_review = AsyncMock(return_value=None)
        
        response = client.get("/multi-agent/status/unknown-claim")
        
        assert response.status_code == 404
        
    def test_status_running(self, client, mock_storage, mock_graph):
        """Test status returns running for in-progress claim."""
        mock_storage.get_thread_by_claim = AsyncMock(return_value="test-123")
        mock_storage.get_error = AsyncMock(return_value=None)
        
        # Set up mock state to return "running" status
        mock_state = MagicMock()
        mock_state.values = {"claim_id": "test-123"}
        mock_state.next = ("agent_1",)  # Has next node = running
        mock_graph.aget_state = AsyncMock(return_value=mock_state)
        
        response = client.get("/multi-agent/status/test-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"


class TestPendingReviewsEndpoint:
    """Test pending reviews endpoint."""
    
    def test_get_pending_reviews_empty(self, client, mock_storage):
        """Test get pending reviews when none exist."""
        mock_storage.get_all_pending_reviews = AsyncMock(return_value={})
        
        response = client.get("/multi-agent/pending-reviews")
        
        assert response.status_code == 200
        data = response.json()
        assert "reviews" in data
        assert len(data["reviews"]) == 0
