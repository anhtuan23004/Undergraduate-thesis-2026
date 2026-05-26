"""Human review panel components."""

from __future__ import annotations

import json
from collections.abc import Callable

import streamlit as st

from .constants import HITL_DECISION_LABELS, SEVERITY_COLORS, SEVERITY_LABELS, HITLDecision
from .document_view import render_document_tab_link
from .findings import (
    render_confidence_badge,
    render_evidence_panel,
    render_suggested_updates,
)


def render_human_review_panel(
    state_data: dict,
    on_resume: Callable,
    action_locked: bool = False,
) -> None:
    """Step 3: split-view HITL panel with optional edit JSON."""
    st.subheader(":material/person_search: Bước 3 - Giao diện thẩm định")
    st.warning("Hồ sơ cần thẩm định thủ công. Vui lòng đưa ra quyết định để tiếp tục quy trình.")
    render_document_tab_link(state_data)

    assessment = get_pending_assessment(state_data)
    left_col, right_col = st.columns([1.2, 1.0])

    with left_col:
        with st.container(border=True):
            st.markdown("**Kết quả từ tác tử**")
            render_assessment_findings(assessment)

    with right_col:
        with st.container(border=True):
            st.markdown("**Biểu mẫu quyết định**")
            decision = st.radio(
                "Quyết định",
                options=[d.value for d in HITLDecision],
                horizontal=True,
                format_func=lambda value: HITL_DECISION_LABELS.get(value, value),
                key="hitl_decision",
            )

            notes = st.text_area(
                "Ghi chú",
                height=120,
                placeholder="Nhập ghi chú thẩm định...",
                key="hitl_notes",
            )

            edited_result = None
            if decision == HITLDecision.EDIT.value:
                st.markdown("**Trình sửa dữ liệu có cấu trúc (JSON)**")
                editable_assessment = get_editable_assessment(state_data)
                default_editor_payload = (
                    editable_assessment if editable_assessment else {"valid": False, "issues": []}
                )
                text_value = st.text_area(
                    "Chỉnh sửa dữ liệu JSON do tác tử trích xuất",
                    value=json.dumps(default_editor_payload, ensure_ascii=False, indent=2),
                    height=260,
                    key="hitl_edit_json",
                )
                try:
                    edited_result = json.loads(text_value)
                except json.JSONDecodeError as ex:
                    st.error(f"JSON không hợp lệ: {ex}")
                    return

            if st.button(
                ":material/play_circle: Tiếp tục quy trình",
                type="primary",
                use_container_width=True,
                disabled=action_locked,
            ):
                on_resume(decision, notes, edited_result)


def render_assessment_findings(assessment: dict | None) -> None:
    """Render pending assessment details for human review."""
    if not assessment:
        st.caption("Không có kết quả đánh giá ở bước này")
        return

    st.write(f"Hợp lệ: **{assessment.get('valid', '-')}**")
    st.write(f"Quyết định: **{assessment.get('decision', '-')}**")

    render_confidence_badge(assessment)

    message = assessment.get("message")
    if message:
        st.caption(message)

    issues = assessment.get("issues") or []
    if not issues:
        st.caption("Không có cảnh báo")
    else:
        for issue in issues:
            severity = str(issue.get("severity", "low")).lower()
            icon = SEVERITY_COLORS.get(severity, "⚪")
            severity_label = SEVERITY_LABELS.get(severity, severity)
            code = issue.get("code", "-")
            description = issue.get("description", "")
            reason = issue.get("reason", "")
            reason_text = f" — *{reason}*" if reason else ""
            st.write(f"{icon} [{severity_label}] {code} - {description}{reason_text}")

    evidence = assessment.get("evidence")
    if evidence:
        render_evidence_panel(evidence)

    suggested_updates = assessment.get("suggested_updates")
    if suggested_updates:
        step_key = assessment.get("stage")
        if not step_key:
            inferred_step_key = "completeness"
            evidence_payload = assessment.get("evidence") or {}
            if isinstance(evidence_payload, dict) and "medical_findings" in evidence_payload:
                inferred_step_key = "quality"
            step_key = inferred_step_key
        render_suggested_updates(suggested_updates, step_key=step_key)


def render_agent_review_summary(state_data: dict) -> None:
    """Render a summary of Agent Review node decisions."""
    history = state_data.get("history") or []
    review_entries = [item for item in history if item.get("step") == "agent_review"]

    if not review_entries:
        st.caption("Chưa có dữ liệu duyệt tự động")
        return

    for entry in review_entries:
        stage = entry.get("stage", "-")
        auto_reviewed = entry.get("auto_reviewed", False)
        confidence = entry.get("confidence", 0)
        reason = entry.get("escalation_reason", "")

        if auto_reviewed:
            st.success(
                f"✅ Giai đoạn **{stage}** đã được duyệt tự động "
                f"(Độ tin cậy: {confidence:.0%}, "
                f"Số gợi ý áp dụng: {entry.get('num_suggestions', 0)})"
            )
        else:
            st.warning(f"⚠️ Giai đoạn **{stage}** cần thẩm định thủ công — Lý do: {reason}")


def get_pending_assessment(state_data: dict) -> dict | None:
    """Return the agent result currently awaiting review."""
    if state_data.get("review_stage") == "completeness":
        return state_data.get("agent_1_result")
    if state_data.get("review_stage") == "quality":
        return state_data.get("agent_2_result")
    if state_data.get("review_stage") == "final":
        return state_data.get("final_result")
    if state_data.get("agent_2_result"):
        return state_data.get("agent_2_result")
    return state_data.get("agent_1_result")


def get_editable_assessment(state_data: dict) -> dict | None:
    """Return the payload that an edit decision should submit."""
    if state_data.get("review_stage") == "final":
        return state_data.get("agent_2_result") or state_data.get("final_result")
    return get_pending_assessment(state_data)


_get_pending_assessment = get_pending_assessment
_get_editable_assessment = get_editable_assessment
_render_agent_review_summary = render_agent_review_summary
_render_assessment_findings = render_assessment_findings
