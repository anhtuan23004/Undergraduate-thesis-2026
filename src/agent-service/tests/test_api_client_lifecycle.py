"""Tests for Streamlit API client HTTP session lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

WEB_INTERFACE_DIR = Path(__file__).parents[1] / "interfaces" / "web"
if str(WEB_INTERFACE_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_INTERFACE_DIR))

import api_client  # noqa: E402
from api_client import APIClient  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {"ok": True}
        self.closed = False

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, "kwargs": kwargs})
        return FakeResponse()

    def close(self) -> None:
        self.closed = True


def test_api_client_does_not_set_global_json_content_type(monkeypatch) -> None:
    monkeypatch.setattr(api_client.requests, "Session", FakeSession)

    client = APIClient("http://agent.test")

    assert "Content-Type" not in client._session.headers


def test_upload_document_reuses_session(monkeypatch) -> None:
    monkeypatch.setattr(api_client.requests, "Session", FakeSession)
    monkeypatch.setattr(
        api_client.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("bypassed session")),
    )
    client = APIClient("http://agent.test")

    result = client.upload_document("claim.pdf", b"%PDF-1.4", "application/pdf")

    assert result == {"ok": True}
    assert client._session.calls == [
        {
            "method": "POST",
            "url": "http://agent.test/api/v1/workflows/upload",
            "kwargs": {
                "files": {"file": ("claim.pdf", b"%PDF-1.4", "application/pdf")},
                "timeout": 60,
            },
        }
    ]


def test_api_client_context_manager_closes_session(monkeypatch) -> None:
    monkeypatch.setattr(api_client.requests, "Session", FakeSession)

    with APIClient("http://agent.test") as client:
        session = client._session

    assert session.closed is True
