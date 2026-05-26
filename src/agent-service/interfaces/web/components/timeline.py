"""Workflow timeline, submission, and monitoring components."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import streamlit as st

from .constants import (
    BADGE_BY_STEP_STATUS,
    STEP_ICONS,
    STEP_LABELS,
    STEP_ORDER,
    STEP_TITLES,
    UI_STATE_LABELS,
)
from .findings import (
    render_confidence_badge,
    render_evidence_panel,
    render_issue_details,
    render_medical_findings,
    render_suggested_updates,
)
from .history import format_history_label, render_history_log
from .review_panel import render_agent_review_summary
from .timeline_state import compute_timeline_status, get_ui_state


def render_app_header(current_run_id: str | None, api_url: str) -> None:
    """Render top title section."""
    st.title(":material/health_and_safety: Hệ thống quản lý hồ sơ bồi thường")
    run_short = current_run_id[:8] if current_run_id else "-"
    st.caption(f"Luồng LangGraph có kiểm soát con người | run_id: {run_short} | API: {api_url}")


def render_sidebar(
    on_new_claim: Callable,
    on_select_run: Callable,
    current_run_id: str | None,
    run_history: list[dict],
    api_url: str,
    on_url_change: Callable,
) -> None:
    """Render sidebar controls and run switcher."""
    with st.sidebar:
        st.header(":material/tune: Điều khiển phiên")

        if st.button(":material/add_circle: Hồ sơ mới", type="primary", use_container_width=True):
            on_new_claim()

        new_url = st.text_input("Địa chỉ API", value=api_url)
        if new_url != api_url:
            on_url_change(new_url)
            st.rerun()

        st.toggle("Tự động cập nhật", key="auto_poll_enabled")

        st.subheader(":material/history: Lịch sử xử lý")
        if not run_history:
            st.caption("Chưa có phiên nào")
            return

        runs = list(reversed(run_history[-20:]))
        run_ids = [run.get("run_id") for run in runs if run.get("run_id")]
        if not run_ids:
            st.caption("Không có run_id hợp lệ")
            return

        new_claim_option = "__new_claim__"
        options = [new_claim_option] + run_ids
        default_index = options.index(current_run_id) if current_run_id in options else 0

        selected = st.selectbox(
            "Chọn phiên",
            options=options,
            index=default_index,
            format_func=lambda rid: (
                "🆕 Tạo hồ sơ mới"
                if rid == new_claim_option
                else format_history_label(runs, rid, get_ui_state)
            ),
        )

        if selected == new_claim_option:
            return

        if selected != current_run_id:
            on_select_run(selected)


def render_claim_submission(on_start: Callable) -> None:
    """Step 1: claim submission form with drag and drop upload."""
    st.subheader(":material/assignment_add: Bước 1 - Khởi tạo hồ sơ")
    with st.container(border=True):
        with st.form("claim_submission_form", clear_on_submit=False, border=False):
            col1, col2 = st.columns(2)
            with col1:
                claim_id = st.text_input(
                    "Mã hồ sơ",
                    value=f"CLM-{int(datetime.now().timestamp())}",
                    key="claim_id_input",
                )
            with col2:
                policy_number = st.text_input(
                    "Số hợp đồng",
                    value="POL-2026",
                    key="policy_number_input",
                )

            uploaded_file = st.file_uploader(
                "Kéo-thả tài liệu y tế (PDF/Ảnh)",
                type=["pdf", "png", "jpg", "jpeg"],
                key="submission_upload",
            )

            if uploaded_file is not None:
                st.caption(
                    f"Tệp đã chọn: {uploaded_file.name} | "
                    f"{uploaded_file.type or 'application/octet-stream'} | "
                    f"{uploaded_file.size} bytes"
                )

            submit = st.form_submit_button(
                ":material/play_circle: Chạy quy trình", type="primary", use_container_width=True
            )

        if submit:
            if not uploaded_file:
                st.error("Vui lòng tải tệp trước khi chạy quy trình.")
                return
            on_start(claim_id.strip(), policy_number.strip(), uploaded_file.name, uploaded_file)


def render_monitoring(state_data: dict) -> None:
    """Step 2: workflow monitoring timeline, live status, and history."""
    st.subheader(":material/monitoring: Bước 2 - Theo dõi tiến trình")

    ui_state = get_ui_state(state_data)
    current_step = str(state_data.get("current_step") or "unknown")

    top_col1, top_col2, top_col3 = st.columns(3)
    with top_col1:
        st.metric("Bước hiện tại", current_step, border=True)
    with top_col2:
        st.metric("Mã phiên", (state_data.get("run_id") or "")[:12], border=True)
    with top_col3:
        st.metric(
            "Trạng thái giao diện", UI_STATE_LABELS.get(ui_state, "Không xác định"), border=True
        )

    render_timeline(state_data)
    render_step_messages(state_data)
    render_history_log(state_data.get("history", []))


def render_timeline(state_data: dict) -> None:
    """Render workflow timeline with active and completed nodes."""
    step_status = compute_timeline_status(state_data)
    cols = st.columns(len(STEP_ORDER))

    for idx, step_key in enumerate(STEP_ORDER):
        status = step_status[step_key]
        icon = STEP_ICONS[step_key]
        label = STEP_LABELS[step_key]
        with cols[idx]:
            with st.container(border=True):
                st.markdown(icon)
                st.markdown(f"**{label}**")
                st.markdown(BADGE_BY_STEP_STATUS[status])


def render_step_messages(state_data: dict) -> None:
    """Show detailed message after each step for better readability."""
    st.markdown("**Diễn giải chi tiết theo từng bước**")

    steps = [
        ("completeness", state_data.get("agent_1_result")),
        ("agent_review", None),
        ("quality", state_data.get("agent_2_result")),
        ("human_review", state_data.get("human_review_result")),
        ("final_decision", state_data.get("final_result")),
    ]

    for step_key, payload in steps:
        with st.container(border=True):
            st.markdown(f"**{STEP_TITLES[step_key]}**")

            if step_key == "agent_review":
                render_agent_review_summary(state_data)
                continue

            if not payload:
                st.caption("Chưa có dữ liệu ở bước này")
                continue

            decision = payload.get("decision") or payload.get("status") or "-"
            message = (
                payload.get("message") or payload.get("rejection_reason") or "Không có thông điệp"
            )

            col1, col2 = st.columns([1, 4])
            with col1:
                st.caption("Quyết định")
                st.write(f"**{str(decision).upper()}**")
            with col2:
                st.caption("Thông điệp")
                st.write(message)

            render_confidence_badge(payload)

            issues = payload.get("issues") or payload.get("issues_summary") or []
            if issues:
                render_issue_details(issues)

            evidence = payload.get("evidence")
            if evidence:
                render_evidence_panel(evidence, step_key=step_key)

            medical_findings = payload.get("medical_findings")
            if medical_findings:
                render_medical_findings(medical_findings)

            suggested_updates = payload.get("suggested_updates")
            if suggested_updates:
                render_suggested_updates(suggested_updates, step_key=step_key)

            if step_key == "human_review":
                notes = payload.get("notes")
                if notes:
                    st.caption(f"Ghi chú thẩm định: {notes}")


def render_raw_state(state_data: dict) -> None:
    """Developer helper to inspect current full state payload."""
    with st.expander("Chế độ kỹ thuật: trạng thái quy trình"):
        st.json(state_data)


_compute_timeline_status = compute_timeline_status
