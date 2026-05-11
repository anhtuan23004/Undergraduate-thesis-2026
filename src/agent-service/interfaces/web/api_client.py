"""API client for the Insurance Claims Processing Agent Service."""

from typing import Any

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
        data: dict | None = None,
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
            response = e.response
            if response is not None:
                status_code = response.status_code
                try:
                    response_body: Any = response.json()
                except ValueError:
                    response_body = response.text

                if status_code == 404:
                    return {
                        "error": f"Không tìm thấy tài nguyên: {endpoint}",
                        "error_detail": response_body,
                        "status_code": status_code,
                        "endpoint": endpoint,
                    }

                return {
                    "error": f"Lỗi HTTP {status_code} khi gọi {endpoint}",
                    "error_detail": response_body,
                    "status_code": status_code,
                    "endpoint": endpoint,
                }

            return {"error": str(e), "endpoint": endpoint}
        except requests.exceptions.Timeout:
            return {"error": "Yêu cầu xử lý quá thời gian chờ", "endpoint": endpoint}
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "endpoint": endpoint}

    def start_workflow(
        self,
        claim_id: str,
        policy_number: str,
        input_file: str = "streamlit_upload",
        file_hash: str | None = None,
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
            "file_hash": file_hash,
        }
        return self._request("POST", "/api/v1/workflows/run", data=data, timeout=300)

    def get_workflow_status(self, run_id: str) -> dict:
        """Get current workflow status.

        Args:
            run_id: The workflow run identifier.

        Returns:
            Current workflow state from MongoDB.
        """
        return self._request("GET", f"/api/v1/workflows/status/{run_id}")

    def resume_workflow(
        self,
        run_id: str,
        decision: str,
        notes: str | None = None,
        edited_result: dict | None = None,
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

        return self._request("POST", f"/api/v1/workflows/resume/{run_id}", data=data, timeout=300)

    def continue_workflow(
        self,
        run_id: str,
        note: str | None = None,
    ) -> dict:
        """Continue workflow when paused at a non-human stage.

        Args:
            run_id: The workflow run identifier.
            note: Optional continuation note.

        Returns:
            Updated workflow state after continue.
        """
        data = {"note": note} if note else {}
        return self._request("POST", f"/api/v1/workflows/continue/{run_id}", data=data, timeout=300)

    def upload_document(self, file_name: str, file_bytes: bytes, mime_type: str) -> dict:
        """Upload claim document to agent-service and get server-side file path."""
        url = f"{self.base_url}/api/v1/workflows/upload"
        files = {"file": (file_name, file_bytes, mime_type or "application/octet-stream")}

        try:
            # Use requests.post instead of self._session.post to avoid the session's
            # Content-Type: application/json overriding the multipart/form-data boundary
            response = requests.post(url, files=files, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            response = e.response
            if response is not None:
                try:
                    response_body: Any = response.json()
                except ValueError:
                    response_body = response.text
                return {
                    "error": f"Lỗi HTTP {response.status_code} khi tải tài liệu lên",
                    "error_detail": response_body,
                    "status_code": response.status_code,
                    "endpoint": "/api/v1/workflows/upload",
                }
            return {"error": str(e), "endpoint": "/api/v1/workflows/upload"}
        except requests.exceptions.Timeout:
            return {
                "error": "Tải tài liệu lên quá thời gian chờ",
                "endpoint": "/api/v1/workflows/upload",
            }
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "endpoint": "/api/v1/workflows/upload"}

    def start_workflow_stream(
        self,
        claim_id: str,
        policy_number: str,
        input_file: str = "streamlit_upload",
        file_hash: str | None = None,
    ):
        """Start a new workflow and yield SSE events as dicts.

        Args:
            claim_id: Unique claim identifier.
            policy_number: Insurance policy number.
            input_file: Source file identifier.
            file_hash: Optional SHA-256 hash of the uploaded file.

        Yields:
            Tuple of (event_type: str, payload: dict) for each SSE event.
        """
        url = f"{self.base_url}/api/v1/workflows/run-stream"
        data = {
            "claim_id": claim_id,
            "policy_number": policy_number,
            "input_file": input_file,
            "file_hash": file_hash,
        }
        yield from self._consume_sse_stream("POST", url, json_data=data)

    def stream_events(self, run_id: str):
        """Stream SSE events for an existing workflow run.

        Args:
            run_id: The workflow run identifier.

        Yields:
            Tuple of (event_type: str, payload: dict) for each SSE event.
        """
        url = f"{self.base_url}/api/v1/workflows/stream/{run_id}"
        yield from self._consume_sse_stream("GET", url)

    def _consume_sse_stream(
        self,
        method: str,
        url: str,
        json_data: dict | None = None,
    ):
        """Low-level SSE consumer that parses event/data lines.

        Args:
            method: HTTP method (GET or POST).
            url: Full URL to stream from.
            json_data: Optional JSON body for POST requests.

        Yields:
            Tuple of (event_type: str, payload: dict).
        """
        import json as _json

        try:
            if method.upper() == "POST":
                resp = self._session.post(url, json=json_data, stream=True, timeout=600)
            else:
                resp = self._session.get(url, stream=True, timeout=600)

            resp.raise_for_status()

            event_type = "message"
            data_lines: list[str] = []

            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue

                line = raw_line

                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:") :].strip())
                elif line == "":
                    # WHY: Empty line is the SSE event boundary.
                    if data_lines:
                        raw_data = "\n".join(data_lines)
                        try:
                            payload = _json.loads(raw_data)
                        except _json.JSONDecodeError:
                            payload = {"raw": raw_data}
                        yield (event_type, payload)
                    event_type = "message"
                    data_lines = []

        except requests.exceptions.RequestException as e:
            yield ("error", {"error": str(e)})

    def health_check(self) -> dict:
        """Check API health status.

        Returns:
            Health status response.
        """
        return self._request("GET", "/api/v1/health")


def create_client(base_url: str | None = None) -> APIClient:
    """Create a new API client instance.

    Args:
        base_url: Optional base URL override.

    Returns:
        APIClient instance.
    """
    return APIClient(base_url=base_url or "http://localhost:8003")
