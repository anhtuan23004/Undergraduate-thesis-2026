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
    render_claim_identity_summary(state_data)
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


def render_claim_identity_summary(state_data: dict) -> None:
    """Render stable claim identity fields on the final dashboard."""
    summary = claim_identity_summary(state_data)

    with st.container(border=True):
        st.markdown("**Thông tin hồ sơ**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Mã hồ sơ**\n\n{summary['claim_id']}")
        with col2:
            st.write(f"**Người được bảo hiểm**\n\n{summary['insured_name']}")
        with col3:
            st.write(f"**Số hợp đồng**\n\n{summary['policy_number']}")


def claim_identity_summary(state_data: dict) -> dict[str, str]:
    """Return reviewer-facing identity fields from workflow state."""
    return {
        "claim_id": _display_value(state_data.get("claim_id")),
        "insured_name": _display_value(_insured_name_from_state(state_data)),
        "policy_number": _display_value(
            state_data.get("policy_number") or _nested_first_value(state_data, POLICY_NUMBER_KEYS)
        ),
    }


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


INSURED_NAME_KEYS = {
    "patient_name",
    "insured_name",
    "insured_person_name",
    "beneficiary_name",
    "claimant_name",
    "customer_name",
    "full_name",
    "ho_ten",
    "hoten",
    "name_of_insured",
}

POLICY_NUMBER_KEYS = {
    "policy_number",
    "contract_number",
    "insurance_policy_number",
    "so_hop_dong",
    "so_hd",
}

EMPTY_DISPLAY_VALUES = {"", "-", "—", "none", "null", "n/a", "na", "unknown"}


def _insured_name_from_state(state_data: dict) -> object:
    priority_sources = (
        (state_data.get("agent_1_result") or {}).get("evidence"),
        (state_data.get("agent_2_result") or {}).get("evidence"),
        (state_data.get("final_result") or {}).get("evidence"),
        state_data.get("extracted_documents"),
    )
    for source in priority_sources:
        value = _nested_first_value(source, INSURED_NAME_KEYS)
        if _has_display_value(value):
            return value
    return None


def _nested_first_value(payload: object, keys: set[str]) -> object:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _normalized_key(key) in keys and _has_display_value(value):
                return value
        for value in payload.values():
            nested = _nested_first_value(value, keys)
            if _has_display_value(nested):
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _nested_first_value(item, keys)
            if _has_display_value(nested):
                return nested
    return None


def _normalized_key(key: object) -> str:
    return str(key or "").strip().lower().replace(" ", "_").replace("-", "_")


def _display_value(value: object) -> str:
    if not _has_display_value(value):
        return "—"
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if _has_display_value(item)) or "—"
    return str(value).strip()


def _has_display_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return any(_has_display_value(item) for item in value)
    return str(value).strip().lower() not in EMPTY_DISPLAY_VALUES
