"""Streamlit UI for Insurance Claims Processing Multi-Agent System.

This application demonstrates the multi-agent workflow with human-in-the-loop
capabilities for insurance claims processing.
"""

from datetime import datetime
from typing import Optional

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from api_client import create_client
from components import (
    render_claim_input_form,
    render_error,
    render_step_flow,
    render_raw_state,
    render_sidebar,
    render_success,
    render_workflow_status,
    render_info,
    WorkflowStatus,
    get_status,
)

DEFAULT_API_URL = "http://localhost:8003"


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    defaults = {
        "current_run_id": None,
        "workflow_state_data": None,
        "is_waiting_human": False,
        "is_stage_paused": False,
        "run_history": [],
        "api_base_url": DEFAULT_API_URL,
        "client": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_client():
    """Get or create the API client."""
    if st.session_state.client is None:
        st.session_state.client = create_client(st.session_state.api_base_url)
    return st.session_state.client


def handle_new_claim() -> None:
    """Handle new claim button click."""
    st.session_state.current_run_id = None
    st.session_state.workflow_state_data = None
    st.session_state.is_waiting_human = False
    st.session_state.is_stage_paused = False
    st.rerun()


def handle_select_run(run_id: str) -> None:
    """Handle run selection from history."""
    st.session_state.current_run_id = run_id
    st.rerun()


def handle_url_change(new_url: str) -> None:
    """Handle API URL change."""
    st.session_state.api_base_url = new_url
    st.session_state.client = create_client(new_url)


def handle_start_workflow(
    claim_id: str,
    policy_number: str,
    input_file: str = "streamlit_upload",
    uploaded_file: Optional[UploadedFile] = None,
) -> None:
    """Handle workflow start request."""
    client = get_client()

    if uploaded_file is not None:
        with st.spinner("Đang upload tài liệu..."):
            upload_result = client.upload_document(
                file_name=uploaded_file.name,
                file_bytes=uploaded_file.getvalue(),
                mime_type=uploaded_file.type or "application/octet-stream",
            )

        if upload_result.get("error"):
            render_error(f"Upload thất bại: {upload_result['error']}")
            return

        input_file = upload_result.get("file_path", input_file)

    with st.spinner("Đang xử lý..."):
        result = client.start_workflow(
            claim_id=claim_id,
            policy_number=policy_number,
            input_file=input_file,
        )

    if result.get("error"):
        render_error(result["error"])
        return

    st.session_state.current_run_id = result.get("run_id")
    st.session_state.workflow_state_data = result
    st.session_state.is_waiting_human = result.get("pending_human_review", False)
    st.session_state.is_stage_paused = bool(result.get("paused", False))

    st.session_state.run_history.append(
        {
            "run_id": result.get("run_id"),
            "claim_id": claim_id,
            "timestamp": datetime.now().isoformat(),
            "data": result,
        }
    )

    if st.session_state.is_waiting_human:
        render_info("Hồ sơ cần được xem xét bởi chuyên viên.")
    elif st.session_state.is_stage_paused:
        render_info("Đã hoàn thành một chặng. Nhấn tiếp tục để chạy bước kế tiếp.")
    else:
        render_success("Xử lý hoàn tất!")

    st.rerun()


def handle_resume_workflow(
    decision: str,
    notes: Optional[str],
) -> None:
    """Handle human review resume request."""
    client = get_client()
    run_id = st.session_state.current_run_id

    if not run_id:
        render_error("Không tìm thấy phiên đang xử lý.")
        return

    with st.spinner("Đang gửi quyết định..."):
        result = client.resume_workflow(
            run_id=run_id,
            decision=decision,
            notes=notes,
        )

    if result.get("error"):
        render_error(result["error"])
        return

    st.session_state.workflow_state_data = result
    st.session_state.is_waiting_human = result.get("pending_human_review", False)
    st.session_state.is_stage_paused = bool(result.get("paused", False))

    for run in st.session_state.run_history:
        if run["run_id"] == run_id:
            run["data"] = result
            break

    render_success("Đã gửi quyết định thành công!")
    st.rerun()


def handle_continue_workflow() -> None:
    """Handle continue request for non-human stage pause."""
    client = get_client()
    run_id = st.session_state.current_run_id

    if not run_id:
        render_error("Không tìm thấy phiên đang xử lý.")
        return

    with st.spinner("Đang tiếp tục xử lý bước kế tiếp..."):
        result = client.continue_workflow(run_id=run_id)

    if result.get("error"):
        render_error(result["error"])
        return

    st.session_state.workflow_state_data = result
    st.session_state.is_waiting_human = result.get("pending_human_review", False)
    st.session_state.is_stage_paused = bool(result.get("paused", False))

    for run in st.session_state.run_history:
        if run["run_id"] == run_id:
            run["data"] = result
            break

    if st.session_state.is_waiting_human:
        render_info("Đã chuyển sang bước cần duyệt thủ công.")
    elif st.session_state.is_stage_paused:
        render_info("Đã hoàn thành thêm một chặng và đang tạm dừng.")
    else:
        render_success("Xử lý hoàn tất!")

    st.rerun()


def handle_refresh_status() -> None:
    """Handle status refresh request."""
    client = get_client()
    run_id = st.session_state.current_run_id

    if not run_id:
        return

    result = client.get_workflow_status(run_id)

    if result.get("error"):
        render_error(result["error"])
        return

    st.session_state.workflow_state_data = result
    st.session_state.is_waiting_human = result.get("pending_human_review", False)
    st.session_state.is_stage_paused = bool(result.get("paused", False))

    for run in st.session_state.run_history:
        if run["run_id"] == run_id:
            run["data"] = result
            break

    status = get_status(result)
    if status == WorkflowStatus.COMPLETED:
        render_success("Xử lý hoàn tất!")
    elif status == WorkflowStatus.PENDING_REVIEW:
        render_info("Hồ sơ đang chờ xem xét.")
    elif status == WorkflowStatus.PAUSED:
        render_info("Workflow đang tạm dừng theo từng chặng.")
    elif status == WorkflowStatus.ERROR:
        render_error(result.get("error", "Unknown error"))

    st.rerun()


def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="Insurance Claims Processing",
        page_icon="🏥",
        layout="wide",
    )

    init_session_state()

    st.title("🏥 Hệ Thống Xử Lý Bồi Thường Bảo Hiểm")
    st.caption("Demo Multi-Agent AI với Human-in-the-Loop")

    render_sidebar(
        on_new_claim=handle_new_claim,
        on_select_run=handle_select_run,
        current_run_id=st.session_state.current_run_id,
        run_history=st.session_state.run_history,
        api_url=st.session_state.api_base_url,
        on_url_change=handle_url_change,
    )

    st.divider()

    if st.session_state.workflow_state_data:
        if st.button("🔄 Làm Mới Trạng Thái"):
            handle_refresh_status()

        render_workflow_status(st.session_state.workflow_state_data)
        st.divider()
        render_step_flow(
            st.session_state.workflow_state_data,
            on_continue=handle_continue_workflow,
            on_resume=handle_resume_workflow,
        )

    elif st.session_state.current_run_id:
        handle_refresh_status()

    else:
        render_claim_input_form(
            on_start=handle_start_workflow,
        )

    st.divider()
    run_id_display = (
        st.session_state.current_run_id[:8]
        if st.session_state.current_run_id
        else "None"
    )
    st.caption(f"Session: {run_id_display} | API: {st.session_state.api_base_url}")


if __name__ == "__main__":
    main()
