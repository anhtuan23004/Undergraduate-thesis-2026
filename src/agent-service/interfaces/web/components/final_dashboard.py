"""Final decision dashboard components."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from .document_view import render_document_tab_link
from .formatters import friendly_decision
from .history import render_history_log


def render_final_dashboard(state_data: dict) -> None:
    """Step 4: final decision card, details, and audit log."""
    st.subheader(":material/gavel: Bước 4 - Kết quả cuối cùng")
    render_document_tab_link(state_data)
    final_result = state_data.get("final_result") or {}

    decision = str(final_result.get("decision") or "").lower()
    approved_amount = final_result.get("approved_amount") or 0
    message = final_result_message(final_result)

    with st.container(border=True):
        decision_label = friendly_decision(decision).upper()
        if decision == "approve":
            st.success(decision_label)
        else:
            st.error(decision_label)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Số tiền bồi thường", f"{approved_amount:,}")
        with col2:
            st.write(f"**{final_message_heading(decision)}**")
            st.write(message)

        issues_summary = final_result.get("issues_summary") or []
        if issues_summary:
            st.markdown("**Tổng hợp vấn đề**")
            st.dataframe(
                pd.DataFrame(format_issues_summary(issues_summary)),
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("**Nhật ký kiểm toán toàn quy trình**")
    render_history_log(state_data.get("history", []))

    st.download_button(
        ":material/download: Tải báo cáo kết quả (JSON)",
        data=json.dumps(state_data, ensure_ascii=False, indent=2),
        file_name=f"claim_report_{state_data.get('run_id', 'unknown')}.json",
        mime="application/json",
        use_container_width=True,
    )


def final_message_heading(decision: str) -> str:
    """Return the Vietnamese heading for the final decision explanation."""
    return "Lý do từ chối" if decision == "reject" else "Diễn giải"


def final_result_message(final_result: dict) -> str:
    """Return a Vietnamese-facing final result message."""
    decision = str(final_result.get("decision") or "").lower()
    if decision == "reject":
        return (
            final_result.get("rejection_reason")
            or _translate_known_final_message(final_result.get("message"))
            or "Hồ sơ bị từ chối. Vui lòng xem phần tổng hợp vấn đề để biết chi tiết."
        )
    return final_result.get("message") or "Hồ sơ được phê duyệt."


def format_issues_summary(issues_summary: list[dict]) -> list[dict]:
    """Format final issue summary rows with Vietnamese labels."""
    return [
        {
            "Nhóm vấn đề": _issue_category_label(item.get("category")),
            "Số lượng": item.get("count", "-"),
            "Mức độ": _severity_label(item.get("severity")),
        }
        for item in issues_summary
        if isinstance(item, dict)
    ]


def _issue_category_label(category: object) -> str:
    labels = {
        "completeness": "Tính đầy đủ hồ sơ",
        "quality": "Chất lượng y tế",
        "policy": "Quy tắc bảo hiểm",
    }
    return labels.get(str(category or "").lower(), str(category or "-"))


def _severity_label(severity: object) -> str:
    labels = {
        "critical": "Nghiêm trọng",
        "high": "Cao",
        "medium": "Trung bình",
        "low": "Thấp",
    }
    return labels.get(str(severity or "").lower(), str(severity or "-"))


def _translate_known_final_message(message: object) -> str | None:
    text = str(message or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if "final decision rejected by reviewer" in lowered:
        return text.split(":", 1)[-1].strip() or "Thẩm định viên từ chối kết luận cuối cùng."
    if "reviewer rejected the final decision" in lowered:
        return "Thẩm định viên từ chối kết luận cuối cùng."
    return text
