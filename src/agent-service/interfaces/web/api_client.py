"""API client for the Insurance Claims Processing Agent Service."""

from typing import Any, Optional

import requests


class APIClient:
    """Client for interacting with the agent service API."""

    def __init__(self, base_url: str = "http://localhost:8003"):
        self.base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        timeout: int = 30,
    ) -> dict:
        """Make HTTP request to the API.

        Args:
            method: HTTP method (GET, POST).
            endpoint: API endpoint path.
            data: Request body data.
            timeout: Request timeout in seconds.

        Returns:
            Response JSON as dict.

        Raises:
            requests.exceptions.RequestException: On network error.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == "GET":
                response = self._session.get(url, timeout=timeout)
            elif method.upper() == "POST":
                response = self._session.post(url, json=data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return {"error": f"Resource not found: {endpoint}"}
            return {"error": str(e)}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def start_workflow(
        self,
        claim_id: str,
        policy_number: str,
        input_file: str = "streamlit_upload",
    ) -> dict:
        """Start a new claim processing workflow.

        Args:
            claim_id: Unique claim identifier.
            policy_number: Insurance policy number.
            input_file: Source file identifier.

        Returns:
            API response with run_id and initial state.
        """
        data = {
            "claim_id": claim_id,
            "policy_number": policy_number,
            "input_file": input_file,
        }
        return self._request("POST", "/api/v2/workflows/run", data=data, timeout=300)

    def get_workflow_status(self, run_id: str) -> dict:
        """Get current workflow status.

        Args:
            run_id: The workflow run identifier.

        Returns:
            Current workflow state from MongoDB.
        """
        return self._request("GET", f"/api/v2/workflows/status/{run_id}")

    def resume_workflow(
        self,
        run_id: str,
        decision: str,
        notes: Optional[str] = None,
        edited_result: Optional[dict] = None,
    ) -> dict:
        """Resume workflow after human review decision.

        Args:
            run_id: The workflow run identifier.
            decision: Human decision (approve, reject, edit).
            notes: Optional reviewer notes.
            edited_result: Optional edited result for 'edit' decision.

        Returns:
            Updated workflow state after resume.
        """
        data = {
            "decision": decision,
            "notes": notes,
        }
        if edited_result:
            data["edited_result"] = edited_result

        return self._request(
            "POST", f"/api/v2/workflows/resume/{run_id}", data=data, timeout=300
        )

    def continue_workflow(
        self,
        run_id: str,
        note: Optional[str] = None,
    ) -> dict:
        """Continue workflow when paused at a non-human stage.

        Args:
            run_id: The workflow run identifier.
            note: Optional continuation note.

        Returns:
            Updated workflow state after continue.
        """
        data = {"note": note} if note else {}
        return self._request(
            "POST", f"/api/v2/workflows/continue/{run_id}", data=data, timeout=300
        )

    def upload_document(self, file_name: str, file_bytes: bytes, mime_type: str) -> dict:
        """Upload claim document to agent-service and get server-side file path."""
        url = f"{self.base_url}/api/v2/workflows/upload"
        files = {"file": (file_name, file_bytes, mime_type or "application/octet-stream")}

        try:
            # Use requests.post instead of self._session.post to avoid the session's 
            # Content-Type: application/json overriding the multipart/form-data boundary
            response = requests.post(url, files=files, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            return {"error": str(e)}
        except requests.exceptions.Timeout:
            return {"error": "Upload timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def health_check(self) -> dict:
        """Check API health status.

        Returns:
            Health status response.
        """
        return self._request("GET", "/api/v2/health")


def create_client(base_url: Optional[str] = None) -> APIClient:
    """Create a new API client instance.

    Args:
        base_url: Optional base URL override.

    Returns:
        APIClient instance.
    """
    return APIClient(base_url=base_url or "http://localhost:8003")
