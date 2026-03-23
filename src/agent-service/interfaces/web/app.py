"""Streamlit UI for insurance claims workflow with HITL review."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from api_client import create_client
from components import (
    STEP_LABELS,
    UIState,
    get_ui_state,
    render_app_header,
    render_brand_theme,
    render_claim_submission,
    render_error_state,
    render_final_dashboard,
    render_human_review_panel,
    render_monitoring,
    render_raw_state,
    render_sidebar,
)

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


DEFAULT_API_URL = "http://localhost:8003"
POLLING_INTERVAL_MS = 2500


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    defaults = {
        "current_run_id": None,
        "workflow_state_data": None,
        "run_history": [],
        "api_base_url": DEFAULT_API_URL,
        "client": None,
        "auto_poll_enabled": True,
        "workflow_action_lock": False,
        "paused_continue_button_disabled": False,
        "pending_paused_continue_request": False,
        "refresh_in_flight": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_client():
    """Get or create API client from current base URL."""
    if st.session_state.client is None:
        st.session_state.client = create_client(st.session_state.api_base_url)
    return st.session_state.client


def handle_new_claim() -> None:
    """Reset active run and cached state for a new submission."""
    st.session_state.current_run_id = None
    st.session_state.workflow_state_data = None
    st.session_state.paused_continue_button_disabled = False
    st.session_state.pending_paused_continue_request = False
    st.session_state.refresh_in_flight = False
    st.rerun()


def handle_select_run(run_id: str) -> None:
    """Switch to an existing run from history."""
    st.session_state.current_run_id = run_id
    st.session_state.paused_continue_button_disabled = False
    st.session_state.pending_paused_continue_request = False
    st.session_state.refresh_in_flight = False
    refresh_status(silent=True)
    st.rerun()


def handle_url_change(new_url: str) -> None:
    """Update API base URL and recreate client."""
    st.session_state.api_base_url = new_url.strip()
    st.session_state.client = create_client(st.session_state.api_base_url)


def upsert_run_history(run_id: Optional[str], claim_id: Optional[str], payload: dict) -> None:
    """Insert or update run history row by run_id."""
    if not run_id:
        return

    for item in st.session_state.run_history:
        if item.get("run_id") == run_id:
            item["data"] = payload
            item["updated_at"] = datetime.now().isoformat()
            return

    st.session_state.run_history.append(
        {
            "run_id": run_id,
            "claim_id": claim_id or payload.get("claim_id"),
            "timestamp": datetime.now().isoformat(),
            "data": payload,
        }
    )


def handle_start_workflow(
    claim_id: str,
    policy_number: str,
    input_file: str = "streamlit_upload",
    uploaded_file: Optional[UploadedFile] = None,
) -> None:
    """Upload file then run workflow with real-time SSE streaming.

    Args:
        claim_id: Unique claim identifier.
        policy_number: Insurance policy number.
        input_file: Source file identifier.
        uploaded_file: Optional Streamlit uploaded file.
    """
    client = get_client()
    file_hash = None

    if uploaded_file is not None:
        with st.spinner("Đang tải tài liệu lên..."):
            upload_result = client.upload_document(
                file_name=uploaded_file.name,
                file_bytes=uploaded_file.getvalue(),
                mime_type=uploaded_file.type or "application/octet-stream",
            )

        if upload_result.get("error"):
            render_error_state(
                f"Tải tệp thất bại: {upload_result['error']}",
                error_payload=upload_result,
                context_label="upload",
            )
            return

        input_file = upload_result.get("file_path", input_file)
        file_hash = upload_result.get("file_hash")

    # WHY: Use SSE streaming to show each step's result immediately.
    last_state = _consume_stream_events(
        client.start_workflow_stream(
            claim_id=claim_id,
            policy_number=policy_number,
            input_file=input_file,
            file_hash=file_hash,
        ),
        status_label="Đang xử lý hồ sơ...",
    )

    if last_state:
        st.session_state.workflow_state_data = last_state
        upsert_run_history(
            st.session_state.current_run_id, claim_id, last_state
        )

    st.rerun()


def _consume_stream_events(
    event_iter,
    status_label: str = "Đang xử lý...",
) -> Optional[dict]:
    """Shared helper to display SSE stream events via st.status.

    Args:
        event_iter: Iterable of (event_type, payload) tuples from APIClient.
        status_label: Initial label for the st.status widget.

    Returns:
        Final state dict, or None on error.
    """
    status = st.status(status_label, expanded=True)
    last_state = None

    for event_type, payload in event_iter:
        if event_type == "run_started":
            run_id = payload.get("run_id")
            st.session_state.current_run_id = run_id
            status.write(f"🚀 Workflow khởi tạo — run_id: `{run_id[:8]}`")

        elif event_type == "node_start":
            step_label = STEP_LABELS.get(payload.get("step"), payload.get("node", ""))
            status.write(f"⏳ Đang xử lý: **{step_label}**...")

        elif event_type == "node_end":
            step_label = STEP_LABELS.get(payload.get("step"), payload.get("node", ""))
            status.write(f"✅ Hoàn thành: **{step_label}**")
            last_state = payload.get("state", last_state)
            if last_state:
                st.session_state.workflow_state_data = last_state

        elif event_type == "done":
            last_state = payload
            status.update(label="Xử lý hoàn tất!", state="complete", expanded=False)

        elif event_type == "error":
            status.update(label="Lỗi xử lý!", state="error")
            render_error_state(
                payload.get("error", "Unknown streaming error"),
                error_payload=payload,
                context_label="stream workflow",
            )
            return None

    return last_state


def handle_resume_workflow(
    decision: str,
    notes: Optional[str],
    edited_result: Optional[dict] = None,
) -> None:
    """Submit human review decision and continue workflow.

    Args:
        decision: Human review decision (approve, reject, edit).
        notes: Optional reviewer comments.
        edited_result: Optional edited result dict for 'edit' decisions.
    """
    if st.session_state.workflow_action_lock:
        return

    run_id = st.session_state.current_run_id
    if not run_id:
        render_error_state("Không tìm thấy run_id để tiếp tục workflow")
        return

    # WHY: Reset the continue flags so handle_continue_workflow is not triggered
    # on the next rerun after this resume call completes.
    st.session_state.pending_paused_continue_request = False
    st.session_state.paused_continue_button_disabled = False
    st.session_state.workflow_action_lock = True
    try:
        client = get_client()
        with st.spinner("Đang gửi quyết định thẩm định..."):
            result = client.resume_workflow(
                run_id=run_id,
                decision=decision,
                notes=notes,
                edited_result=edited_result,
            )

        if result.get("error"):
            render_error_state(
                result["error"],
                error_payload=result,
                context_label="resume workflow",
            )
            return

        st.session_state.workflow_state_data = result
        upsert_run_history(run_id, result.get("claim_id"), result)
        st.rerun()
    finally:
        st.session_state.workflow_action_lock = False


def handle_continue_workflow() -> None:
    """Continue paused workflow stage with real-time streaming."""
    run_id = st.session_state.current_run_id
    if not run_id:
        render_error_state("Không tìm thấy run_id để tiếp tục bước xử lý")
        return

    try:
        client = get_client()
        last_state = _consume_stream_events(
            client.stream_events(run_id),
            status_label="Đang tiếp tục xử lý...",
        )

        if last_state:
            st.session_state.workflow_state_data = last_state
            upsert_run_history(run_id, last_state.get("claim_id"), last_state)
        st.rerun()
    finally:
        st.session_state.paused_continue_button_disabled = False
        st.session_state.pending_paused_continue_request = False


def refresh_status(silent: bool = False) -> Optional[dict]:
    """Fetch latest workflow status from API by current run_id."""
    run_id = st.session_state.current_run_id
    if not run_id:
        return None

    try:
        st.session_state.refresh_in_flight = True
        client = get_client()
        result = client.get_workflow_status(run_id)
        if result.get("error"):
            if not silent:
                render_error_state(
                    result["error"],
                    error_payload=result,
                    context_label="lấy trạng thái workflow",
                )
            return None

        st.session_state.workflow_state_data = result
        upsert_run_history(run_id, result.get("claim_id"), result)
        return result
    finally:
        st.session_state.refresh_in_flight = False


def render_auto_polling(state_data: dict) -> None:
    """Poll status every 2.5s while workflow is actively processing.

    WHY: We deliberately skip polling for WAITING_FOR_HUMAN:
    the human must explicitly submit a decision. Auto-refresh during this
    state would cause repeated resume calls and an infinite loop.
    """
    ui_state = get_ui_state(state_data)
    should_poll = (
        st.session_state.auto_poll_enabled
        and st.session_state.current_run_id
        and ui_state == UIState.PROCESSING  # Only poll while actively processing
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
    data = st.session_state.workflow_state_data

    if data is None and st.session_state.current_run_id:
        data = refresh_status(silent=True)

    if data is None:
        render_claim_submission(on_start=handle_start_workflow)
        return

    if st.session_state.pending_paused_continue_request:
        handle_continue_workflow()
        return

    # Disable refresh button during processing states to prevent duplicate API calls
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

    render_auto_polling(data)
    data = st.session_state.workflow_state_data or data

    render_monitoring(data)
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


def main() -> None:
    """Streamlit app entry point."""
    st.set_page_config(
        page_title="Hệ thống bồi thường bảo hiểm",
        page_icon=":material/health_and_safety:",
        layout="wide",
    )

    init_session_state()
    render_brand_theme()

    render_sidebar(
        on_new_claim=handle_new_claim,
        on_select_run=handle_select_run,
        current_run_id=st.session_state.current_run_id,
        run_history=st.session_state.run_history,
        api_url=st.session_state.api_base_url,
        on_url_change=handle_url_change,
    )

    render_app_header(
        current_run_id=st.session_state.current_run_id,
        api_url=st.session_state.api_base_url,
    )

    render_main_content()

    if st.toggle("Chế độ developer", key="developer_mode") and st.session_state.workflow_state_data:
        render_raw_state(st.session_state.workflow_state_data)


if __name__ == "__main__":
    main()
