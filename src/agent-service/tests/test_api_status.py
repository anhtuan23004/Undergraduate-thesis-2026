"""Tests for status API error contracts."""

from types import SimpleNamespace

import pytest
from api.status import get_workflow_status
from fastapi import HTTPException


async def test_get_workflow_status_not_found_uses_standard_error(monkeypatch):
    class Graph:
        async def aget_state(self, _config):
            return SimpleNamespace(values=None)

    async def get_graph():
        return Graph()

    monkeypatch.setattr("api.status.get_graph", get_graph)

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_status("missing-run")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "error": "Run missing-run not found",
        "error_detail": None,
        "status_code": 404,
        "endpoint": "/workflows/status",
    }
