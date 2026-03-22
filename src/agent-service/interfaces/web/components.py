"""Streamlit UI components for Insurance Claims Processing."""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import streamlit as st


class WorkflowStatus(str, Enum):
    """Workflow status indicators."""

    COMPLETED = "completed"
    PENDING_REVIEW = "pending_review"
    PAUSED = "paused"
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
    WorkflowStatus.PAUSED: "🟠",
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
    if state_data.get("paused"):
        return WorkflowStatus.PAUSED
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
            # Show up to 10 most recent runs, most recent first
            recent_runs = list(reversed(run_history[-10:]))
            run_ids = [run["run_id"] for run in recent_runs if run.get("run_id")]

            def _format_run_label(run_id: str) -> str:
                run = next((r for r in recent_runs if r.get("run_id") == run_id), None)
                if not run:
                    return run_id
                status = get_status(run.get("data"))
                status_emoji = STATUS_EMOJIS.get(status, "⚪")
                display_id = run_id[:8] if run_id else "N/A"
                return f"{status_emoji} {display_id}..."

            if run_ids:
                # Default to the current run if it is in the history
                if current_run_id in run_ids:
                    default_index = run_ids.index(current_run_id)
                else:
                    default_index = None

                selected_run_id = st.radio(
                    "Chọn phiên",
                    options=run_ids,
                    index=default_index if default_index is not None else 0,
                    format_func=_format_run_label,
                    key="run_history_selection",
                )

                if selected_run_id and selected_run_id != current_run_id:
                    on_select_run(selected_run_id)

def render_claim_input_form(on_start: Callable) -> None:
    """Render the form for submitting a new claim."""
    st.subheader("📝 Thông Tin Hồ Sơ")
    col1, col2 = st.columns(2)
    with col1:
        claim_id = st.text_input("Mã Hồ Sơ (Claim ID)", value=f"CLM-{int(datetime.now().timestamp())}")
    with col2:
        policy_number = st.text_input("Mã Hợp Đồng (Policy Number)", value="POL-2024")

    st.subheader("📎 Tài Liệu Bồi Thường")
    uploaded_file = st.file_uploader(
        "Upload tài liệu (PDF/Ảnh/JSON/TXT)",
        type=["pdf", "png", "jpg", "jpeg", "json", "txt"],
        help="Có thể upload tài liệu gốc; nếu là JSON OCR thì hệ thống sẽ đọc tự động.",
    )

    if uploaded_file is not None:
        st.caption(
            f"File đã chọn: {uploaded_file.name} | "
            f"{uploaded_file.type or 'application/octet-stream'} | "
            f"{uploaded_file.size} bytes"
        )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Bắt Đầu Phân Tích", use_container_width=True, type="primary"):
            if uploaded_file is None:
                st.error("Vui lòng upload tài liệu trước khi bắt đầu.")
            else:
                input_file = uploaded_file.name
                on_start(claim_id, policy_number, input_file, uploaded_file)


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
            agent_msg = result.get("message")
            if agent_msg:
                st.info(f"**Thông điệp:** {agent_msg}")

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
    st.warning("⚠️ **Hệ thống phát hiện dữ liệu không nhất quán. Cần chuyên viên y tế can thiệp!**")

    st.subheader("📋 Thông Tin Can Thiệp")

    col1, col2 = st.columns(2)
    with col1:
        waiting_at = (
            "Completeness Check" if not state_data.get("agent_2_result") else "Quality Check"
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

    if st.button("⚡ Gửi Quyết Định & Tiếp Tục", type="primary", use_container_width=True):
        on_resume(action, notes)


def render_stage_pause_panel(
    state_data: dict,
    on_continue: Callable,
) -> None:
    """Render pause panel for stage-by-stage execution mode."""
    pause_at = state_data.get("pause_at", "unknown")
    stage_labels = {
        "quality_check": "Quality Check",
        "final_decision": "Final Decision",
    }
    next_stage = stage_labels.get(pause_at, pause_at)

    st.info("⏸️ **Đã hoàn thành một chặng và tạm dừng theo luồng mới.**")
    st.write(f"**Bước kế tiếp:** {next_stage}")
    st.caption("Nhấn tiếp tục để chạy sang bước tiếp theo của workflow.")

    if st.button("▶️ Tiếp Tục Workflow", type="primary", use_container_width=True):
        on_continue()


def _render_result_summary(result: Optional[dict]) -> None:
    """Render compact summary for one step result."""
    if not result:
        st.caption("Chưa có kết quả ở bước này.")
        return

    decision = result.get("decision", result.get("status", result.get("valid")))
    if decision in ("accept", "approve", True):
        st.success(f"Kết luận: {decision}")
    elif decision in ("reject", False):
        st.error(f"Kết luận: {decision}")
    else:
        st.warning(f"Kết luận: {decision}")

    agent_message = result.get("message")
    if agent_message:
        st.info(f"**Thông điệp:** {agent_message}")

    issues = result.get("issues", []) or []
    if issues:
        st.write("Vấn đề phát hiện:")
        for issue in issues[:5]:
            severity = issue.get("severity", "unknown")
            desc = issue.get("description", issue.get("message", ""))
            emoji = SEVERITY_COLORS.get(severity, "⚪")
            st.write(f"- {emoji} [{severity.upper()}] {desc}")


def _infer_active_step(state_data: dict) -> int:
    """Infer current active step for UI focus.

    Returns:
        1|2|3 for active processing step, 0 when completed.
    """
    if state_data.get("final_result"):
        return 0

    if state_data.get("pending_human_review"):
        review = state_data.get("human_review_result") or {}
        stage = review.get("stage")
        if stage == "quality" or state_data.get("agent_2_result"):
            return 2
        return 1

    if state_data.get("paused"):
        pause_at = state_data.get("pause_at")
        if pause_at == "quality_check":
            return 2
        if pause_at == "final_decision":
            return 3

    if not state_data.get("agent_1_result"):
        return 1
    if not state_data.get("agent_2_result"):
        return 2
    return 3


def render_step_flow(
    state_data: dict,
    on_continue: Callable,
    on_resume: Callable,
) -> None:
    """Render step-by-step workflow UI with action in active step."""
    st.subheader("🧭 Luồng xử Lý Theo Từng Step")

    active_step = _infer_active_step(state_data)
    step_defs = [
        (1, "Step 1: Completeness", state_data.get("agent_1_result")),
        (2, "Step 2: Quality", state_data.get("agent_2_result")),
        (3, "Step 3: Final Decision", state_data.get("final_result")),
    ]

    for idx, title, result in step_defs:
        is_done = result is not None
        is_active = active_step == idx
        prefix = "✅" if is_done else ("🔵" if is_active else "⭕")

        with st.expander(f"{prefix} {title}", expanded=is_active or is_done):
            _render_result_summary(result)

            if is_active and state_data.get("pending_human_review"):
                st.divider()
                render_hitl_panel(state_data, on_resume=on_resume)

            if is_active and state_data.get("paused") and not state_data.get("pending_human_review"):
                st.divider()
                render_stage_pause_panel(state_data, on_continue=on_continue)

    if state_data.get("final_result"):
        st.divider()
        st.subheader("📝 Kết Quả Phê Duyệt Cuối Cùng")
        res = state_data["final_result"]
        
        decision = res.get("decision", "").upper()
        if decision == "APPROVE" or decision == "ACCEPT":
            st.success(f"✅ QUYẾT ĐỊNH: CHẤP NHẬN BỒI THƯỜNG")
            amount = res.get("approved_amount")
            if amount is not None:
                st.write(f"**Số tiền duyệt chi:** {amount:,} VNĐ")
        else:
            st.error(f"❌ QUYẾT ĐỊNH: TỪ CHỐI BỒI THƯỜNG")
            reason = res.get("rejection_reason")
            if reason:
                st.write(f"**Lý do từ chối:** {reason}")
                
        st.info(f"**Thông điệp từ hệ thống:** {res.get('message', '')}")
        
        issues = res.get("issues_summary", [])
        if issues:
            st.write("**Tổng hợp vấn đề:**")
            for issue in issues:
                cat = issue.get("category", "")
                count = issue.get("count", 0)
                sev = issue.get("severity", "")
                st.write(f"- {cat.title()}: {count} lỗi (Mức độ: {sev.title()})")


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
