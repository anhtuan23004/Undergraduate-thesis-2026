"""Streamlit UI components for Insurance Claims Processing."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import streamlit as st


class WorkflowStatus(str, Enum):
    """Workflow status indicators."""

    COMPLETED = "completed"
    PENDING_REVIEW = "pending_review"
    RUNNING = "running"
    ERROR = "error"


class HITLDecision(str, Enum):
    """Human-in-the-loop decision options."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

STATUS_EMOJIS = {
    WorkflowStatus.COMPLETED: "🟢",
    WorkflowStatus.PENDING_REVIEW: "🟡",
    WorkflowStatus.RUNNING: "🔵",
    WorkflowStatus.ERROR: "🔴",
}


def get_status(state_data: Optional[dict]) -> WorkflowStatus:
    """Determine workflow status from state data."""
    if not state_data:
        return WorkflowStatus.RUNNING
    if state_data.get("error"):
        return WorkflowStatus.ERROR
    if state_data.get("pending_human_review"):
        return WorkflowStatus.PENDING_REVIEW
    if state_data.get("final_result"):
        return WorkflowStatus.COMPLETED
    if state_data.get("current_step", "").startswith("completed_"):
        return WorkflowStatus.COMPLETED
    return WorkflowStatus.RUNNING


def render_sidebar(
    on_new_claim: Callable,
    on_select_run: Callable,
    current_run_id: Optional[str],
    run_history: list,
    api_url: str,
    on_url_change: Callable,
) -> None:
    """Render the sidebar with session management.

    Args:
        on_new_claim: Callback for new claim button.
        on_select_run: Callback for selecting a run.
        current_run_id: Currently selected run ID.
        run_history: List of previous runs.
        api_url: Current API URL.
        on_url_change: Callback when URL changes.
    """
    with st.sidebar:
        st.header("📋 Quản Lý Phiên")

        if st.button("➕ Tạo Hồ Sơ Mới", use_container_width=True):
            on_new_claim()

        st.divider()
        st.subheader("Lịch Sử Phiên")

        if not run_history:
            st.caption("Chưa có phiên nào")
        else:
            for run in reversed(run_history[-10:]):
                col1, col2 = st.columns([4, 1])
                status = get_status(run.get("data"))
                status_emoji = STATUS_EMOJIS.get(status, "⚪")

                with col1:
                    display_id = run["run_id"][:8] if run["run_id"] else "N/A"
                    is_selected = current_run_id == run["run_id"]
                    prefix = "**" if is_selected else ""
                    suffix = "**" if is_selected else ""
                    st.code(
                        f"{prefix}{status_emoji} {display_id}...{suffix}", language=None
                    )

                with col2:
                    if st.button("Chọn", key=f"select_{run['run_id']}"):
                        on_select_run(run["run_id"])

        st.divider()

        with st.expander("⚙️ Cài Đặt"):
            new_url = st.text_input("API URL", value=api_url, key="api_url_input")
            if st.button("Cập Nhật"):
                on_url_change(new_url)
                st.success("Đã cập nhật API URL")


def render_claim_input_form(
    on_start: Callable,
    default_ocr_data: Optional[dict] = None,
) -> None:
    """Render the claim input form.

    Args:
        on_start: Callback when workflow should start.
        default_ocr_data: Default OCR data to populate.
    """
    st.subheader("📝 Thông Tin Hồ Sơ")

    col1, col2 = st.columns(2)
    with col1:
        claim_id = st.text_input("Mã Hồ Sơ", value="CLM-001", key="claim_id")
        policy_number = st.text_input(
            "Số Hợp Đồng", value="POL-2024-001", key="policy_number"
        )

    with col2:
        benefit_type = st.selectbox(
            "Loại Bảo Hiểm",
            ["health insurance", "dental", "vision", "life"],
            key="benefit_type",
        )
        task_type = st.selectbox(
            "Loại Xử Lý",
            [
                "full-flow",
                "med-verification",
                "document-extraction",
                "verify-diagnosis",
            ],
            key="task_type",
        )

    st.subheader("📄 Dữ Liệu OCR (JSON)")
    default_json = json.dumps(
        default_ocr_data
        or {
            "patient_name": "Nguyễn Văn A",
            "diagnosis": "Pneumonia (J12.9)",
            "medications": ["Amoxicillin 500mg", "Paracetamol 500mg"],
            "treatment_date": "2024-01-15",
            "hospital": "Bệnh viện Đại học Y dược",
            "total_amount": 15000000,
        },
        indent=2,
        ensure_ascii=False,
    )
    ocr_data_str = st.text_area(
        "Dán dữ liệu OCR từ service OCR",
        value=default_json,
        height=200,
        key="ocr_data",
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Bắt Đầu Phân Tích", use_container_width=True, type="primary"):
            try:
                ocr_data = json.loads(ocr_data_str)
                on_start(claim_id, policy_number, ocr_data)
            except json.JSONDecodeError:
                st.error("Dữ liệu OCR không hợp lệ. Vui lòng kiểm tra định dạng JSON.")


def render_workflow_status(state_data: dict) -> None:
    """Render the workflow status dashboard.

    Args:
        state_data: Current workflow state.
    """
    history = state_data.get("history", [])

    st.subheader("📊 Tiến Trình Xử Lý")

    steps = [
        ("completeness_check", "Agent 1: Kiểm Tra Tính Đầy Đủ", "📋"),
        ("quality_check", "Agent 2: Kiểm Tra Chất Lượng Y Tế", "🏥"),
        ("final_decision", "Agent 3: Kết Luận Cuối Cùng", "✅"),
    ]

    completed_steps = {
        entry.get("step", "").replace("completed_", "")
        for entry in history
        if entry.get("step", "").startswith("completed_")
    }

    cols = st.columns(3)
    for idx, (step_key, step_name, icon) in enumerate(steps):
        with cols[idx]:
            if step_key in completed_steps or state_data.get("final_result"):
                st.success(f"{icon} {step_name}\n✓ Hoàn Thành")
            elif idx == 0 or list(steps)[idx - 1][0] in completed_steps:
                st.info(f"{icon} {step_name}\n⏳ Đang Xử Lý")
            else:
                st.caption(f"{icon} {step_name}\n⭕ Chưa Bắt Đầu")

    st.divider()

    for entry in history:
        render_agent_result(entry)


def render_agent_result(entry: dict) -> None:
    """Render a single agent result card.

    Args:
        entry: Agent result entry from history.
    """
    agent_name = entry.get("agent", "Unknown")
    result = entry.get("result", {})

    with st.expander(f"📦 Kết Quả: {agent_name}", expanded=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            decision = result.get("decision", result.get("valid", False))
            if decision == "accept" or decision is True:
                st.success("✅ Chấp Nhận")
            elif decision == "reject" or decision is False:
                st.error("❌ Từ Chối")
            else:
                st.warning("⚠️ Cần Xem Xét")

        with col2:
            issues = result.get("issues", [])
            if issues:
                st.write("**Vấn Đề Phát Hiện:**")
                for issue in issues:
                    severity = issue.get("severity", "unknown")
                    desc = issue.get("description", issue.get("message", ""))
                    emoji = SEVERITY_COLORS.get(severity, "⚪")
                    st.write(f"{emoji} [{severity.upper()}] {desc}")


def render_hitl_panel(
    state_data: dict,
    on_resume: Callable,
) -> None:
    """Render the Human-in-the-Loop review panel.

    Args:
        state_data: Current workflow state.
        on_resume: Callback when decision is submitted.
    """
    st.warning(
        "⚠️ **Hệ thống phát hiện dữ liệu không nhất quán. "
        "Cần chuyên viên y tế can thiệp!**"
    )

    st.subheader("📋 Thông Tin Can Thiệp")

    col1, col2 = st.columns(2)
    with col1:
        waiting_at = (
            "Completeness Check"
            if not state_data.get("agent_2_result")
            else "Quality Check"
        )
        st.info(f"**Đang chờ tại:** {waiting_at}")

        agent_result = (
            state_data.get("agent_1_result")
            if not state_data.get("agent_2_result")
            else state_data.get("agent_2_result")
        )
        if agent_result and "issues" in agent_result:
            st.write("**Lý do dừng:**")
            for issue in agent_result.get("issues", [])[:3]:
                st.write(f"- {issue.get('description', issue.get('message', ''))}")

    with col2:
        st.write("**Hành động của bạn:**")
        decision_labels = {
            "approve": "✅ Chấp Nhận - Cho phép tiếp tục xử lý",
            "reject": "❌ Từ Chối - Bác bỏ hồ sơ",
            "edit": "✏️ Yêu Cầu Sửa Đổi - Cần bổ sung thông tin",
        }

        def _format_decision(x: Any) -> str:
            return decision_labels.get(x, str(x))

        action = st.selectbox(
            "Quyết định",
            options=[h.value for h in HITLDecision],
            format_func=_format_decision,
        )

    notes = st.text_area("Ghi Chú (Tuỳ Chọn)", height=100, key="hitl_notes")

    if st.button(
        "⚡ Gửi Quyết Định & Tiếp Tục", type="primary", use_container_width=True
    ):
        on_resume(action, notes)


def render_raw_state(state_data: dict) -> None:
    """Render the raw graph state in developer mode.

    Args:
        state_data: Current workflow state.
    """
    with st.expander("🛠️ Xem Trạng Thái Graph (Developer Mode)"):
        st.json(state_data)


def render_error(message: str) -> None:
    """Render an error message.

    Args:
        message: Error message to display.
    """
    st.error(f"❌ Lỗi: {message}")


def render_success(message: str) -> None:
    """Render a success message.

    Args:
        message: Success message to display.
    """
    st.success(f"✅ {message}")


def render_info(message: str) -> None:
    """Render an info message.

    Args:
        message: Info message to display.
    """
    st.info(message)
