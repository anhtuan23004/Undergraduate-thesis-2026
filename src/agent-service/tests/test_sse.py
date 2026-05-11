"""Tests for workflow server-sent event helpers."""

from api.sse import NODE_TO_STEP


def test_sse_step_map_includes_ocr_extraction() -> None:
    assert NODE_TO_STEP["ocr_extraction"] == "ocr_extraction"
