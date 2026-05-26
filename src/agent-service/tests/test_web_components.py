"""Lightweight tests for pure Streamlit UI helper logic."""

from __future__ import annotations

import sys
import types
from importlib import import_module

from interfaces.web.components import (
    StepStatus,
    UIState,
    compute_timeline_status,
    friendly_decision,
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
    assert friendly_decision("approve") == "Phê duyệt"
    assert friendly_decision("reject") == "Từ chối"
    assert friendly_decision("accept_with_edit") == "Cần chỉnh sửa"
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


def test_final_reject_prefers_vietnamese_rejection_reason() -> None:
    final_dashboard = _final_dashboard_module()
    result = {
        "decision": "reject",
        "message": "Final decision rejected by reviewer: Missing invoice",
        "rejection_reason": "Thiếu hóa đơn viện phí",
    }

    assert final_dashboard.final_result_message(result) == "Thiếu hóa đơn viện phí"


def test_format_issues_summary_uses_vietnamese_labels() -> None:
    final_dashboard = _final_dashboard_module()
    rows = final_dashboard.format_issues_summary(
        [{"category": "completeness", "count": 2, "severity": "high"}]
    )

    assert rows == [
        {
            "Nhóm vấn đề": "Tính đầy đủ hồ sơ",
            "Số lượng": 2,
            "Mức độ": "Cao",
        }
    ]


def test_claim_identity_summary_uses_completeness_evidence_patient_name() -> None:
    final_dashboard = _final_dashboard_module()

    summary = final_dashboard.claim_identity_summary(
        {
            "claim_id": "CLM-001",
            "policy_number": "POL-001",
            "agent_1_result": {
                "evidence": {
                    "patient_name": "Nguyễn Văn A",
                    "policy_number": "POL-EVIDENCE",
                }
            },
        }
    )

    assert summary == {
        "claim_id": "CLM-001",
        "insured_name": "Nguyễn Văn A",
        "policy_number": "POL-001",
    }


def test_claim_identity_summary_falls_back_to_extracted_documents() -> None:
    final_dashboard = _final_dashboard_module()

    summary = final_dashboard.claim_identity_summary(
        {
            "claim_id": "CLM-002",
            "extracted_documents": {
                "documents": [
                    {
                        "document_name": "Giấy khám bệnh",
                        "extracted_data": {
                            "insured_person_name": "Trần Thị B",
                            "so_hop_dong": "POL-002",
                        },
                    }
                ]
            },
        }
    )

    assert summary == {
        "claim_id": "CLM-002",
        "insured_name": "Trần Thị B",
        "policy_number": "POL-002",
    }


def _final_dashboard_module():
    pandas = types.ModuleType("pandas")
    pandas.DataFrame = lambda rows: rows
    sys.modules.setdefault("pandas", pandas)

    streamlit = types.ModuleType("streamlit")
    streamlit.__getattr__ = lambda name: lambda *args, **kwargs: None
    sys.modules.setdefault("streamlit", streamlit)

    sys.modules.pop("interfaces.web.components.final_dashboard", None)
    return import_module("interfaces.web.components.final_dashboard")
