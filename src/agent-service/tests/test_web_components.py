"""Lightweight tests for pure Streamlit UI helper logic."""

from __future__ import annotations

import sys
import types
from importlib import import_module

from interfaces.web.components import (
    StepStatus,
    UIState,
    compute_timeline_status,
    friendly_status,
    friendly_step_name,
    get_ui_state,
)


def test_get_ui_state_prefers_explicit_workflow_status() -> None:
    assert get_ui_state({"workflow_status": "waiting_human"}) == UIState.WAITING_FOR_HUMAN
    assert get_ui_state({"workflow_status": "completed"}) == UIState.COMPLETED
    assert get_ui_state({"workflow_status": "error"}) == UIState.ERROR


def test_compute_timeline_status_uses_explicit_active_stage() -> None:
    status = compute_timeline_status(
        {
            "workflow_status": "running",
            "active_stage": "quality",
            "agent_1_result": {"is_auto_reviewed": True},
        }
    )

    assert status["completeness"] == StepStatus.DONE
    assert status["agent_review"] == StepStatus.DONE
    assert status["quality"] == StepStatus.ACTIVE


def test_compute_timeline_status_marks_human_review_waiting() -> None:
    status = compute_timeline_status(
        {
            "workflow_status": "waiting_human",
            "review_stage": "completeness",
            "agent_1_result": {"decision": "approve"},
            "pending_human_review": True,
        }
    )

    assert status["completeness"] == StepStatus.DONE
    assert status["agent_review"] == StepStatus.DONE
    assert status["human_review"] == StepStatus.WAITING


def test_history_formatters() -> None:
    assert friendly_step_name("quality_agent") == "Kiểm tra chất lượng y tế"
    assert friendly_step_name("final_decision") == "Kết luận cuối cùng"
    assert friendly_status("approve", {}) == "Đạt"
    assert friendly_status("reject", {}) == "Không đạt"
    assert friendly_status("-", {"error": "boom"}) == "Lỗi"


def test_workflow_document_url_uses_run_id_and_api_base_url() -> None:
    streamlit = types.ModuleType("streamlit")
    streamlit.session_state = {"api_base_url": "http://localhost:8003/"}
    sys.modules["streamlit"] = streamlit
    sys.modules.pop("interfaces.web.components.document_view", None)

    workflow_document_url = import_module(
        "interfaces.web.components.document_view"
    ).workflow_document_url

    assert (
        workflow_document_url({"run_id": "run 1"})
        == "http://localhost:8003/api/v1/workflows/document/run%201"
    )
