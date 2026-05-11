"""Main render orchestration for the Streamlit web UI."""

from __future__ import annotations

import streamlit as st
from app_actions import (
    handle_continue_workflow,
    handle_resume_workflow,
    handle_start_workflow,
    refresh_status,
)
from components import (
    UIState,
    get_ui_state,
    render_claim_submission,
    render_error_state,
    render_final_dashboard,
    render_human_review_panel,
    render_monitoring,
)

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


POLLING_INTERVAL_MS = 2500


def render_auto_polling(state_data: dict) -> None:
    """Poll status while workflow is actively processing."""
    ui_state = get_ui_state(state_data)
    should_poll = (
        st.session_state.auto_poll_enabled
        and st.session_state.current_run_id
        and ui_state == UIState.PROCESSING
    )

    if not should_poll:
        return

    if st_autorefresh is not None:
        st_autorefresh(interval=POLLING_INTERVAL_MS, key=f"poll_{st.session_state.current_run_id}")
        refresh_status(silent=True)
        st.caption("Tự động cập nhật trạng thái mỗi 2.5 giây")
        return

    st.warning(
        "Tính năng tự động cập nhật cần package 'streamlit-autorefresh'. "
        "Vui lòng cài dependencies trong src/agent-service/requirements.txt."
    )


def render_main_content() -> None:
    """Render full UI according to current workflow state."""
    data = _current_workflow_data()

    if data is None:
        render_claim_submission(on_start=handle_start_workflow)
        return

    if st.session_state.pending_paused_continue_request:
        handle_continue_workflow()
        return

    _render_refresh_button(data)
    render_auto_polling(data)
    data = st.session_state.workflow_state_data or data

    render_monitoring(data)
    render_state_detail(data)


def _current_workflow_data() -> dict | None:
    data = st.session_state.workflow_state_data
    if data is None and st.session_state.current_run_id:
        return refresh_status(silent=True)
    return data


def _render_refresh_button(data: dict) -> None:
    ui_state = get_ui_state(data)
    disable_refresh = (
        st.session_state.refresh_in_flight
        or st.session_state.workflow_action_lock
        or ui_state in (UIState.PROCESSING, UIState.WAITING_FOR_HUMAN)
    )

    if st.button(
        ":material/refresh: Làm mới trạng thái",
        disabled=disable_refresh,
    ):
        refresh_status()


def render_state_detail(data: dict) -> None:
    """Render the lower detail panel for the current UI state."""
    ui_state = get_ui_state(data)

    if ui_state == UIState.WAITING_FOR_HUMAN:
        render_human_review_panel(
            data,
            on_resume=handle_resume_workflow,
            action_locked=st.session_state.workflow_action_lock,
        )
        return

    if ui_state == UIState.COMPLETED:
        render_final_dashboard(data)
        return

    if ui_state == UIState.ERROR:
        render_error_state(
            str(data.get("error") or "Lỗi workflow không xác định"),
            error_payload=data,
            context_label="workflow",
        )
        if st.button(
            ":material/replay: Thử chạy tiếp",
            type="primary",
        ):
            handle_continue_workflow()
        return

    if data.get("paused") and not data.get("pending_human_review"):
        st.info("Workflow đang tạm dừng ở một bước tự động")
        if st.button(
            ":material/play_circle: Tiếp tục bước tạm dừng",
            type="primary",
            disabled=st.session_state.paused_continue_button_disabled,
        ):
            st.session_state.paused_continue_button_disabled = True
            st.session_state.pending_paused_continue_request = True
            st.rerun()
