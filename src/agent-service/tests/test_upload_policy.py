"""Tests for upload validation and path policy."""

from __future__ import annotations

from types import SimpleNamespace

from api.upload import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_upload_rejects_unsupported_extension() -> None:
    response = _client().post(
        "/api/v1/workflows/upload",
        files={"file": ("claim.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    assert "Phần mở rộng tệp không được hỗ trợ" in response.json()["detail"]


def test_upload_rejects_unsupported_mime_type() -> None:
    response = _client().post(
        "/api/v1/workflows/upload",
        files={"file": ("claim.pdf", b"%PDF-1.4", "text/plain")},
    )

    assert response.status_code == 415
    assert "Loại MIME của tệp không được hỗ trợ" in response.json()["detail"]


def test_upload_rejects_extension_mime_mismatch() -> None:
    response = _client().post(
        "/api/v1/workflows/upload",
        files={"file": ("claim.pdf", b"not really a png", "image/png")},
    )

    assert response.status_code == 415
    assert "Phần mở rộng tệp không khớp với loại MIME" in response.json()["detail"]


def test_upload_rejects_oversized_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("api.upload.settings.UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr("api.upload.settings.MAX_UPLOAD_SIZE_MB", 0)

    response = _client().post(
        "/api/v1/workflows/upload",
        files={"file": ("claim.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 413
    assert "Tệp quá lớn" in response.json()["detail"]


def test_upload_saves_allowed_file_with_safe_basename(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("api.upload.settings.UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr("api.upload.settings.MAX_UPLOAD_SIZE_MB", 20)

    response = _client().post(
        "/api/v1/workflows/upload",
        files={"file": ("../claim.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "claim.pdf"
    assert payload["file_path"].startswith(str(tmp_path))
    assert payload["size_bytes"] == len(b"%PDF-1.4")


def test_view_workflow_document_serves_uploaded_file(monkeypatch, tmp_path) -> None:
    input_file = tmp_path / "claim.pdf"
    input_file.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr("api.upload.settings.UPLOADS_DIR", str(tmp_path))

    class FakeGraph:
        async def aget_state(self, config):
            return SimpleNamespace(values={"input_file": str(input_file)})

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr("api.upload.get_graph", fake_get_graph)

    response = _client().get("/api/v1/workflows/document/run-1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4"


def test_view_workflow_document_rejects_missing_run(monkeypatch) -> None:
    class FakeGraph:
        async def aget_state(self, config):
            return None

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr("api.upload.get_graph", fake_get_graph)

    response = _client().get("/api/v1/workflows/document/missing-run")

    assert response.status_code == 404
