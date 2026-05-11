"""Workflow action handlers for the Streamlit web UI."""

from __future__ import annotations

import streamlit as st
from app_session import get_client, reset_workflow_flags, upsert_run_history
from app_streams import consume_stream_events
from components import render_error_state
from streamlit.runtime.uploaded_file_manager import UploadedFile


def handle_new_claim() -> None:
    """Reset active run and cached state for a new submission."""
    st.session_state.current_run_id = None
    st.session_state.workflow_state_data = None
    reset_workflow_flags()
    st.rerun()


def handle_select_run(run_id: str) -> None:
    """Switch to an existing run from history."""
    st.session_state.current_run_id = run_id
    st.session_state.workflow_state_data = None
    reset_workflow_flags()
    refresh_status(silent=True)
    st.rerun()


def handle_url_change(new_url: str) -> None:
    """Update API base URL and recreate client."""
    st.session_state.api_base_url = new_url.strip()
    st.session_state.client = None


def handle_start_workflow(
    claim_id: str,
    policy_number: str,
    input_file: str = "streamlit_upload",
    uploaded_file: UploadedFile | None = None,
) -> None:
    """Upload file then run workflow with real-time SSE streaming."""
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

    last_state = consume_stream_events(
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
        upsert_run_history(st.session_state.current_run_id, claim_id, last_state)

    st.rerun()


def handle_resume_workflow(
    decision: str,
    notes: str | None,
    edited_result: dict | None = None,
) -> None:
    """Submit human review decision and continue workflow."""
    if st.session_state.workflow_action_lock:
        return

    run_id = st.session_state.current_run_id
    if not run_id:
        render_error_state("Không tìm thấy run_id để tiếp tục workflow")
        return

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
    if st.session_state.workflow_action_lock:
        return

    run_id = st.session_state.current_run_id
    if not run_id:
        render_error_state("Không tìm thấy run_id để tiếp tục bước xử lý")
        return

    st.session_state.workflow_action_lock = True
    try:
        client = get_client()
        last_state = consume_stream_events(
            client.stream_events(run_id),
            status_label="Đang tiếp tục xử lý...",
        )

        if last_state:
            st.session_state.workflow_state_data = last_state
            upsert_run_history(run_id, last_state.get("claim_id"), last_state)
        st.rerun()
    finally:
        st.session_state.workflow_action_lock = False
        st.session_state.paused_continue_button_disabled = False
        st.session_state.pending_paused_continue_request = False


def refresh_status(silent: bool = False) -> dict | None:
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
