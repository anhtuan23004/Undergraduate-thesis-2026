"""Streamlit UI components for insurance claims workflow monitoring and review."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import pandas as pd
import streamlit as st


class UIState(str, Enum):
    """Primary UI states used by the app."""

    PROCESSING = "processing"
    WAITING_FOR_HUMAN = "waiting_for_human"
    ERROR = "error"
    COMPLETED = "completed"


class HITLDecision(str, Enum):
    """Human-in-the-loop decision values sent to API."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class StepStatus(str, Enum):
    """Status for timeline nodes."""

    DONE = "done"
    ACTIVE = "active"
    WAITING = "waiting"
    PENDING = "pending"


SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

STEP_ORDER = ["completeness", "quality", "human_review", "final_decision"]

STEP_LABELS = {
    "completeness": "Kiểm tra tính đầy đủ",
    "quality": "Kiểm tra chất lượng y tế",
    "human_review": "Thẩm định thủ công",
    "final_decision": "Kết luận cuối cùng",
}

STEP_ICONS = {
    "completeness": ":material/checklist:",
    "quality": ":material/medical_services:",
    "human_review": ":material/person_search:",
    "final_decision": ":material/gavel:",
}

BADGE_BY_STEP_STATUS = {
    StepStatus.DONE: ":green-badge[Hoàn thành]",
    StepStatus.ACTIVE: ":blue-badge[Đang xử lý]",
    StepStatus.WAITING: ":orange-badge[Chờ thẩm định]",
    StepStatus.PENDING: ":gray-badge[Chờ bước trước]",
}


def render_brand_theme() -> None:
    """Inject brand-aligned styling for spacing and visual consistency."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');

        :root {
            --brand-primary: #1B8DB6;
            --brand-accent: #34A2CA;
            --brand-bg-soft: #15232D;
            --brand-border: #2D4656;
            --brand-success: #1E8E5A;
            --brand-danger: #C23B35;
            --brand-warning: #BC7A00;
        }

        html, body, [class*="css"] {
            font-family: "Be Vietnam Pro", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(1200px 420px at -10% -20%, rgba(52, 162, 202, 0.14), transparent 62%),
                radial-gradient(1000px 380px at 110% 0%, rgba(27, 141, 182, 0.12), transparent 56%),
                linear-gradient(180deg, #0A1117 0%, #0E171F 55%, #121E27 100%);
            color: #E7F2F8;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0A3E55 0%, #0F4B64 100%);
        }

        [data-testid="stSidebar"] * {
            color: #F3FBFF !important;
        }

        [data-testid="stMarkdownContainer"],
        [data-testid="stText"],
        [data-testid="stCaptionContainer"] {
            color: #E7F2F8;
        }

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlock"] div[data-testid="stContainer"] {
            background: rgba(15, 28, 38, 0.58);
            border-radius: 12px;
        }

        div[data-testid="stMetric"] {
            background: var(--brand-bg-soft);
            border: 1px solid var(--brand-border);
            border-radius: 12px;
            padding: 10px 12px;
            color: #E7F2F8;
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
            border: none;
            border-radius: 10px;
            color: #ffffff;
            font-weight: 600;
        }

        div[data-testid="stButton"] > button {
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_ui_state(state_data: Optional[dict]) -> UIState:
    """Map graph state into one of the four UI states."""
    if not state_data:
        return UIState.PROCESSING
    if state_data.get("error"):
        return UIState.ERROR
    if state_data.get("final_result"):
        return UIState.COMPLETED
    if state_data.get("pending_human_review"):
        return UIState.WAITING_FOR_HUMAN
    return UIState.PROCESSING


def render_app_header(current_run_id: Optional[str], api_url: str) -> None:
    """Render top title section."""
    st.title(":material/health_and_safety: Hệ thống quản lý hồ sơ bồi thường")
    run_short = current_run_id[:8] if current_run_id else "-"
    st.caption(f"Luồng LangGraph có Human-in-the-Loop | run_id: {run_short} | API: {api_url}")


def render_sidebar(
    on_new_claim: Callable,
    on_select_run: Callable,
    current_run_id: Optional[str],
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

        st.toggle("Tự động cập nhật", key="auto_poll_enabled", value=True)

        st.subheader(":material/history: Lịch sử xử lý")
        if not run_history:
            st.caption("Chưa có phiên nào")
            return

        runs = list(reversed(run_history[-20:]))
        run_ids = [r.get("run_id") for r in runs if r.get("run_id")]
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
            format_func=lambda rid: "🆕 Tạo hồ sơ mới" if rid == new_claim_option else _format_history_label(runs, rid),
        )

        if selected == new_claim_option:
            return

        if selected != current_run_id:
            on_select_run(selected)


def _format_history_label(runs: list[dict], run_id: str) -> str:
    run = next((item for item in runs if item.get("run_id") == run_id), {})
    state = get_ui_state(run.get("data"))
    emoji = {
        UIState.PROCESSING: "🟦",
        UIState.WAITING_FOR_HUMAN: "🟨",
        UIState.ERROR: "🟥",
        UIState.COMPLETED: "🟩",
    }.get(state, "⬜")
    claim = run.get("claim_id", "-")
    return f"{emoji} {run_id[:8]} | {claim}"


def render_claim_submission(on_start: Callable) -> None:
    """Step 1: claim submission form with drag and drop upload."""
    st.subheader(":material/assignment_add: Bước 1 - Khởi tạo hồ sơ")
    with st.container(border=True):
        with st.form("claim_submission_form", clear_on_submit=False, border=False):
            col1, col2 = st.columns(2)
            with col1:
                claim_id = st.text_input(
                    "Mã hồ sơ (Claim ID)",
                    value=f"CLM-{int(datetime.now().timestamp())}",
                    key="claim_id_input",
                )
            with col2:
                policy_number = st.text_input(
                    "Số hợp đồng (Policy Number)",
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

            submit = st.form_submit_button(":material/play_circle: Chạy workflow", type="primary", use_container_width=True)

        if submit:
            if not uploaded_file:
                st.error("Vui lòng tải tệp trước khi chạy workflow.")
                return
            on_start(claim_id.strip(), policy_number.strip(), uploaded_file.name, uploaded_file)


def render_monitoring(state_data: dict) -> None:
    """Step 2: workflow monitoring timeline + live status + history."""
    st.subheader(":material/monitoring: Bước 2 - Theo dõi tiến trình")

    ui_state = get_ui_state(state_data)
    current_step = str(state_data.get("current_step") or "unknown")

    top_col1, top_col2, top_col3 = st.columns(3)
    with top_col1:
        st.metric("Bước hiện tại", current_step, border=True)
    with top_col2:
        st.metric("Mã phiên", (state_data.get("run_id") or "")[:12], border=True)
    with top_col3:
        st.metric("Trạng thái UI", ui_state.value.upper(), border=True)

    render_timeline(state_data)
    render_step_messages(state_data)
    render_history_log(state_data.get("history", []))


def render_timeline(state_data: dict) -> None:
    """Render 4-step timeline with active and completed nodes."""
    step_status = _compute_timeline_status(state_data)
    cols = st.columns(4)

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
        (
            "completeness",
            "Bước 1 - Kiểm tra tính đầy đủ",
            state_data.get("agent_1_result"),
        ),
        (
            "quality",
            "Bước 2 - Kiểm tra chất lượng y tế",
            state_data.get("agent_2_result"),
        ),
        (
            "human_review",
            "Bước 3 - Kết quả thẩm định thủ công",
            state_data.get("human_review_result"),
        ),
        (
            "final_decision",
            "Bước 4 - Kết luận cuối cùng",
            state_data.get("final_result"),
        ),
    ]

    for step_key, title, payload in steps:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            if not payload:
                st.caption("Chưa có dữ liệu ở bước này")
                continue

            decision = payload.get("decision") or payload.get("status") or "-"
            message = payload.get("message") or payload.get("rejection_reason") or "Không có message"

            col1, col2 = st.columns([1, 4])
            with col1:
                st.caption("Quyết định")
                st.write(f"**{str(decision).upper()}**")
            with col2:
                st.caption("Message")
                st.write(message)

            issues = payload.get("issues") or payload.get("issues_summary") or []
            if issues:
                _render_issue_details(issues)

            if step_key == "human_review":
                notes = payload.get("notes")
                if notes:
                    st.caption(f"Ghi chú thẩm định: {notes}")


def _render_issue_details(issues: list[dict]) -> None:
    """Render issue list in a clear and reviewer-friendly format."""
    st.markdown("**Lỗi / Cảnh báo chi tiết**")

    rows = []
    for issue in issues:
        severity = str(issue.get("severity", "low")).lower()
        icon = SEVERITY_COLORS.get(severity, "⚪")
        code = issue.get("code") or issue.get("category") or "-"
        description = issue.get("description") or issue.get("message") or "-"
        count = issue.get("count")

        if count is not None:
            description = f"{description} (số lượng: {count})"

        rows.append(
            {
                "Mức độ": f"{icon} {severity.upper()}",
                "Mã/Nhóm": str(code),
                "Mô tả": str(description),
            }
        )

    if not rows:
        st.caption("Không có lỗi/cảnh báo")
        return

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Mức độ": st.column_config.TextColumn("Mức độ", width="small"),
            "Mã/Nhóm": st.column_config.TextColumn("Mã/Nhóm", width="small"),
            "Mô tả": st.column_config.TextColumn("Mô tả", width="large"),
        },
    )


def _compute_timeline_status(state_data: dict) -> dict[str, StepStatus]:
    out = {step: StepStatus.PENDING for step in STEP_ORDER}

    if state_data.get("agent_1_result"):
        out["completeness"] = StepStatus.DONE
    if state_data.get("agent_2_result"):
        out["quality"] = StepStatus.DONE
    if state_data.get("human_review_result") and not state_data.get("pending_human_review"):
        out["human_review"] = StepStatus.DONE
    if state_data.get("final_result"):
        out["final_decision"] = StepStatus.DONE
        return out

    current_step = str(state_data.get("current_step") or "").lower()
    if state_data.get("pending_human_review"):
        out["human_review"] = StepStatus.WAITING
        if state_data.get("agent_2_result"):
            out["quality"] = StepStatus.DONE
        elif state_data.get("agent_1_result"):
            out["completeness"] = StepStatus.DONE
        return out

    if "quality" in current_step:
        out["quality"] = StepStatus.ACTIVE
    elif "final" in current_step or "decision" in current_step:
        out["final_decision"] = StepStatus.ACTIVE
    elif "human" in current_step:
        out["human_review"] = StepStatus.ACTIVE
    else:
        out["completeness"] = StepStatus.ACTIVE

    return out


def render_history_log(history: list[dict]) -> None:
    """Render completed actions from graph history list."""
    st.markdown("**Nhật ký hành động**")
    if not history:
        st.caption("Chưa có lịch sử")
        return

    rows = []
    for idx, item in enumerate(history, start=1):
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        step_raw = str(item.get("step") or "unknown")
        step_label = _friendly_step_name(step_raw)

        decision = item.get("decision") or result.get("decision") or result.get("status") or "-"
        status = _friendly_status(decision, result)

        message = (
            result.get("message")
            or result.get("rejection_reason")
            or item.get("notes")
            or result.get("error")
            or "-"
        )

        issues = result.get("issues") or result.get("issues_summary") or []
        issue_count = len(issues) if isinstance(issues, list) else 0

        rows.append(
            {
                "STT": idx,
                "Bước": step_label,
                "Tác nhân": item.get("agent", "System"),
                "Trạng thái": status,
                "Quyết định": str(decision).upper() if decision != "-" else "-",
                "Số lỗi": issue_count,
                "Thông điệp": message,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "STT": st.column_config.NumberColumn("STT", width="small"),
            "Bước": st.column_config.TextColumn("Bước", width="medium"),
            "Tác nhân": st.column_config.TextColumn("Tác nhân", width="small"),
            "Trạng thái": st.column_config.TextColumn("Trạng thái", width="small"),
            "Quyết định": st.column_config.TextColumn("Quyết định", width="small"),
            "Số lỗi": st.column_config.NumberColumn("Số lỗi", width="small"),
            "Thông điệp": st.column_config.TextColumn("Thông điệp", width="large"),
        },
    )


def _friendly_step_name(step_raw: str) -> str:
    raw = step_raw.lower()
    exact_map = {
        "completeness_agent": "Kiểm tra tính đầy đủ",
        "quality_agent": "Kiểm tra chất lượng y tế",
        "decision_agent": "Kết luận cuối cùng",
        "human_review": "Thẩm định thủ công",
        "human_review_complete": "Hoàn tất thẩm định thủ công",
        "manual_continue": "Tiếp tục thủ công",
    }
    if raw in exact_map:
        return exact_map[raw]

    if "completeness" in raw:
        return "Kiểm tra tính đầy đủ"
    if "quality" in raw:
        return "Kiểm tra chất lượng y tế"
    if "human_review" in raw or "human" in raw:
        return "Thẩm định thủ công"
    if "final" in raw or "decision" in raw:
        return "Kết luận cuối cùng"
    if "start" in raw:
        return "Khởi tạo workflow"
    return step_raw


def _friendly_status(decision: Any, result: dict) -> str:
    if result.get("error"):
        return "Lỗi"

    decision_text = str(decision).lower()
    if decision_text in ("approve", "accept", "accepted"):
        return "Đạt"
    if decision_text in ("reject", "rejected"):
        return "Không đạt"
    if decision_text in ("accept_with_edit", "edit"):
        return "Cần chỉnh sửa"
    return "Đã ghi nhận"


def render_human_review_panel(
    state_data: dict,
    on_resume: Callable,
    action_locked: bool = False,
) -> None:
    """Step 3: split-view HITL panel with optional edit JSON."""
    st.subheader(":material/person_search: Bước 3 - Giao diện thẩm định")
    st.warning("Hồ sơ cần thẩm định thủ công. Vui lòng đưa ra quyết định để tiếp tục workflow.")

    assessment = _get_pending_assessment(state_data)
    extracted_documents = state_data.get("extracted_documents") or {}

    left_col, right_col = st.columns([1.2, 1.0])

    with left_col:
        with st.container(border=True):
            st.markdown("**Kết quả từ Agent**")
            _render_assessment_findings(assessment)

        with st.container(border=True):
            st.markdown("**Dữ liệu OCR thô (extracted_documents)**")
            st.json(extracted_documents)

    with right_col:
        with st.container(border=True):
            st.markdown("**Biểu mẫu quyết định**")
            decision = st.radio(
                "Quyết định",
                options=[d.value for d in HITLDecision],
                horizontal=True,
                format_func=lambda value: {
                    "approve": "Phê duyệt",
                    "reject": "Từ chối",
                    "edit": "Chỉnh sửa",
                }.get(value, value),
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
                default_editor_payload = assessment if assessment else {"valid": False, "issues": []}
                text_value = st.text_area(
                    "Chỉnh sửa dữ liệu JSON Agent trích xuất",
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
                ":material/play_circle: Tiếp tục workflow",
                type="primary",
                use_container_width=True,
                disabled=action_locked,
            ):
                on_resume(decision, notes, edited_result)


def _render_assessment_findings(assessment: Optional[dict]) -> None:
    if not assessment:
        st.caption("Không có kết quả đánh giá ở bước này")
        return

    st.write(f"Hợp lệ: **{assessment.get('valid', '-') }**")
    st.write(f"Quyết định: **{assessment.get('decision', '-') }**")
    message = assessment.get("message")
    if message:
        st.caption(message)

    issues = assessment.get("issues") or []
    if not issues:
        st.caption("Không có cảnh báo")
        return

    for issue in issues:
        severity = str(issue.get("severity", "low")).lower()
        icon = SEVERITY_COLORS.get(severity, "⚪")
        code = issue.get("code", "-")
        description = issue.get("description", "")
        st.write(f"{icon} [{severity.upper()}] {code} - {description}")


def _get_pending_assessment(state_data: dict) -> Optional[dict]:
    if state_data.get("agent_2_result"):
        return state_data.get("agent_2_result")
    return state_data.get("agent_1_result")


def render_final_dashboard(state_data: dict) -> None:
    """Step 4: final decision card + details + audit trail."""
    st.subheader(":material/gavel: Bước 4 - Kết quả cuối cùng")
    final_result = state_data.get("final_result") or {}

    decision = str(final_result.get("decision") or "").lower()
    approved_amount = final_result.get("approved_amount") or 0
    message = final_result.get("message") or final_result.get("rejection_reason") or "-"

    with st.container(border=True):
        if decision == "approve":
            st.success("PHÊ DUYỆT")
        else:
            st.error("TỪ CHỐI")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Số tiền bồi thường", f"{approved_amount:,}")
        with col2:
            st.write("**Lý do / diễn giải**")
            st.write(message)

        issues_summary = final_result.get("issues_summary") or []
        if issues_summary:
            st.markdown("**Tổng hợp vấn đề**")
            st.dataframe(pd.DataFrame(issues_summary), hide_index=True, use_container_width=True)

    st.markdown("**Audit trail toàn quy trình**")
    render_history_log(state_data.get("history", []))

    st.download_button(
        ":material/download: Tải báo cáo kết quả (JSON)",
        data=json.dumps(state_data, ensure_ascii=False, indent=2),
        file_name=f"claim_report_{state_data.get('run_id', 'unknown')}.json",
        mime="application/json",
        use_container_width=True,
    )


def render_error_state(
    error_message: str,
    error_payload: Optional[dict] = None,
    context_label: str = "workflow",
) -> None:
    """Render API/workflow error with full details for human review."""
    st.error(f"Lỗi {context_label}: {error_message}")

    with st.container(border=True):
        st.markdown("**Chi tiết lỗi cho Human Review**")

        status_code = None
        endpoint = None
        detail = None
        if isinstance(error_payload, dict):
            status_code = error_payload.get("status_code")
            endpoint = error_payload.get("endpoint")
            detail = error_payload.get("error_detail") or error_payload.get("detail")

        col1, col2 = st.columns(2)
        with col1:
            st.caption("Mã lỗi HTTP")
            st.write(str(status_code) if status_code is not None else "-")
        with col2:
            st.caption("Endpoint")
            st.write(endpoint or "-")

        st.caption("Thông tin chi tiết")
        if detail:
            if isinstance(detail, (dict, list)):
                st.json(detail)
            else:
                st.code(str(detail), language="text")
        else:
            st.write(error_message)

        if isinstance(error_payload, dict):
            with st.expander("Xem payload lỗi đầy đủ"):
                st.json(error_payload)


def render_raw_state(state_data: dict) -> None:
    """Developer helper to inspect current full state payload."""
    with st.expander("Chế độ developer: raw graph state"):
        st.json(state_data)
