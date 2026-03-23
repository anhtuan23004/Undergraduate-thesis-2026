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

STEP_ORDER = ["completeness", "agent_review", "quality", "human_review", "final_decision"]

STEP_LABELS = {
    "completeness": "Kiểm tra đầy đủ",
    "agent_review": "Duyệt tự động",
    "quality": "Kiểm tra chất lượng",
    "human_review": "Thẩm định thủ công",
    "final_decision": "Kết luận cuối cùng",
}

STEP_ICONS = {
    "completeness": ":material/checklist:",
    "agent_review": ":material/verified:",
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
            format_func=lambda rid: (
                "🆕 Tạo hồ sơ mới" if rid == new_claim_option else _format_history_label(runs, rid)
            ),
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

            submit = st.form_submit_button(
                ":material/play_circle: Chạy workflow", type="primary", use_container_width=True
            )

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
        (
            "completeness",
            "Bước 1 - Kiểm tra tính đầy đủ",
            state_data.get("agent_1_result"),
        ),
        (
            "agent_review",
            "Bước 2 - Duyệt tự động (Agent Review)",
            None,  # WHY: Agent review data is embedded in agent results via is_auto_reviewed flag
        ),
        (
            "quality",
            "Bước 3 - Kiểm tra chất lượng y tế",
            state_data.get("agent_2_result"),
        ),
        (
            "human_review",
            "Bước 4 - Kết quả thẩm định thủ công",
            state_data.get("human_review_result"),
        ),
        (
            "final_decision",
            "Bước 5 - Kết luận cuối cùng",
            state_data.get("final_result"),
        ),
    ]

    for step_key, title, payload in steps:
        with st.container(border=True):
            st.markdown(f"**{title}**")

            # WHY: Agent review step is derived from history entries, not a standalone result.
            if step_key == "agent_review":
                _render_agent_review_summary(state_data)
                continue

            if not payload:
                st.caption("Chưa có dữ liệu ở bước này")
                continue

            decision = payload.get("decision") or payload.get("status") or "-"
            message = (
                payload.get("message") or payload.get("rejection_reason") or "Không có message"
            )

            col1, col2 = st.columns([1, 4])
            with col1:
                st.caption("Quyết định")
                st.write(f"**{str(decision).upper()}**")
            with col2:
                st.caption("Message")
                st.write(message)

            # WHY: Show confidence score and auto-review badge for assessment outputs.
            _render_confidence_badge(payload)

            issues = payload.get("issues") or payload.get("issues_summary") or []
            if issues:
                _render_issue_details(issues)

            # WHY: Display evidence extracted by the agent for reviewer transparency.
            evidence = payload.get("evidence")
            if evidence:
                _render_evidence_panel(evidence, step_key=step_key)

            # WHY: Display structured medical findings (success/warnings) for Quality Agent.
            medical_findings = payload.get("medical_findings")
            if medical_findings:
                _render_medical_findings(medical_findings)

            # WHY: Display suggested updates with reference URLs for easy verification.
            suggested_updates = payload.get("suggested_updates")
            if suggested_updates:
                _render_suggested_updates(suggested_updates, step_key=step_key)

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
        reason = issue.get("reason") or "-"
        count = issue.get("count")

        if count is not None:
            description = f"{description} (số lượng: {count})"

        rows.append(
            {
                "Mức độ": f"{icon} {severity.upper()}",
                "Mã/Nhóm": str(code),
                "Mô tả": str(description),
                "Lý do": str(reason),
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
            "Mô tả": st.column_config.TextColumn("Mô tả", width="medium"),
            "Lý do": st.column_config.TextColumn("Lý do", width="medium"),
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
        # WHY: If final_decision is done, mark agent_review as done too.
        if out["completeness"] == StepStatus.DONE:
            out["agent_review"] = StepStatus.DONE
        return out

    current_step = str(state_data.get("current_step") or "").lower()

    # WHY: Detect agent_review states from current_step patterns.
    # NOTE: Check for completed agent-review states before generic "agent_review"
    if "agent_reviewed" in current_step or "agent_review_escalated" in current_step:
        out["agent_review"] = StepStatus.DONE
    elif current_step.startswith("agent_review"):
        out["agent_review"] = StepStatus.ACTIVE
    elif out["completeness"] == StepStatus.DONE and out["quality"] == StepStatus.DONE:
        out["agent_review"] = StepStatus.DONE
    elif out["completeness"] == StepStatus.DONE:
        # WHY: Completeness is done but quality hasn't started → agent_review may be active or done.
        a1_result = state_data.get("agent_1_result") or {}
        if a1_result.get("is_auto_reviewed") is not None:
            out["agent_review"] = StepStatus.DONE

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
    elif "agent_review" not in current_step:
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
        "agent_review": "Duyệt tự động (Agent Review)",
        "verifier_agent": "Xác minh chéo (Verifier)",
    }
    if raw in exact_map:
        return exact_map[raw]

    if "agent_review" in raw or "verifier" in raw:
        return "Duyệt tự động (Agent Review)"
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

        # with st.container(border=True):
        #     st.markdown("**Dữ liệu OCR thô (extracted_documents)**")
        #     st.json(extracted_documents)

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
                default_editor_payload = (
                    assessment if assessment else {"valid": False, "issues": []}
                )
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

    st.write(f"Hợp lệ: **{assessment.get('valid', '-')}**")
    st.write(f"Quyết định: **{assessment.get('decision', '-')}**")

    _render_confidence_badge(assessment)

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
            code = issue.get("code", "-")
            description = issue.get("description", "")
            reason = issue.get("reason", "")
            reason_text = f" — *{reason}*" if reason else ""
            st.write(f"{icon} [{severity.upper()}] {code} - {description}{reason_text}")

    evidence = assessment.get("evidence")
    if evidence:
        _render_evidence_panel(evidence)

    suggested_updates = assessment.get("suggested_updates")
    if suggested_updates:
        # Determine step_key for hitl panel based on result keys if possible
        _render_suggested_updates(suggested_updates, step_key="quality" if "agent_2_result" in str(assessment) else "completeness")


def _render_agent_review_summary(state_data: dict) -> None:
    """Render a summary of what the Agent Review node decided.

    Args:
        state_data: Current workflow state dict.
    """
    history = state_data.get("history") or []
    review_entries = [h for h in history if h.get("step") == "agent_review"]

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

def _render_confidence_badge(payload: dict) -> None:
    """Display a color-coded confidence score badge.

    Args:
        payload: Agent result dict containing confidence_score.
    """
    confidence = payload.get("confidence_score")
    if confidence is None:
        return

    is_auto = payload.get("is_auto_reviewed", False)
    auto_tag = " · ✅ Auto-reviewed" if is_auto else ""

    if confidence >= 0.9:
        color = "green"
    elif confidence >= 0.7:
        color = "orange"
    else:
        color = "red"

    st.markdown(f":{color}-badge[Độ tin cậy: {confidence:.0%}]{auto_tag}")


def _render_medical_findings(findings: dict) -> None:
    """Render structured medical findings (success/warnings) from Quality Agent.

    Args:
        findings: Dict containing status_message, summary, warnings, and success.
    """
    if not findings:
        return

    st.markdown("---")
    st.markdown("### 🔍 Kết quả thẩm định y tế chi tiết")

    # 1. Summary Metrics
    data = findings.get("data", {})
    summary = data.get("summary", {})
    total_w = summary.get("total_warnings", 0)
    total_s = summary.get("total_success", 0)

    # Status indicator
    status = findings.get("status_message", "Warning")
    if status.lower() == "success":
        st.success(f"✅ Hợp lệ: {total_s} danh mục")
    else:
        st.warning(f"⚠️ Cảnh báo: {total_w} lỗi/nghi vấn")

    # 2. Helper to clean and translate findings
    type_labels = {
        "icd_valid": "Mã ICD hợp lệ",
        "coverage_approved": "Đã duyệt quyền lợi",
        "medicine_valid": "Thuốc hợp lệ",
        "icd_missing": "Thiếu mã ICD",
        "icd_mismatch": "Mã ICD không khớp",
        "excluded_diagnosis": "Bệnh lý loại trừ",
        "medicine_mismatch": "Thuốc không phù hợp",
        "name_consistent": "Họ tên đồng nhất",
        "prescription_date_valid": "Ngày kê đơn hợp lệ",
    }

    def clean(val):
        return val if val and str(val).lower() != "none" else "—"

    # 3. Warnings Section
    warnings_list = data.get("warnings", [])
    if warnings_list:
        st.markdown("**🚨 Cảnh báo & Sai sót**")
        w_rows = []
        for w in warnings_list:
            w_type = w.get("type", "")
            # Combine all medical context into one 'Content detail' string
            diag = clean(w.get("diagnosis_name"))
            icd = clean(w.get("suggested_icd"))
            msg = clean(w.get("message"))
            url = w.get("reference_url")

            content = f"{msg}"
            if diag != "—": content = f"**{diag}** - {content}"
            if icd != "—": content = f"[{icd}] {content}"
            if url: content += f" ([Tham chiếu]({url}))"

            w_rows.append({
                "Phân loại": type_labels.get(w_type, w_type.replace("_", " ").title()),
                "Chi tiết nội dung": content,
            })
        
        # Using st.write for markdown support in the content
        for row in w_rows:
            st.markdown(f"- **{row['Phân loại']}:** {row['Chi tiết nội dung']}")

    # 4. Success Section
    success_list = data.get("success", [])
    if success_list:
        st.markdown("**✅ Các mục đã xác thực**")
        s_rows = []
        for s in success_list:
            s_type = s.get("type", "")
            diag = clean(s.get("diagnosis_name"))
            icd = clean(s.get("icd"))
            msg = clean(s.get("message"))
            url = s.get("reference_url")

            content = f"{msg}"
            if diag != "—": content = f"**{diag}** - {content}"
            if icd != "—": content = f"[{icd}] {content}"
            if url: content += f" ([Tham chiếu]({url}))"

            s_rows.append({
                "Phân loại": type_labels.get(s_type, s_type.replace("_", " ").title()),
                "Chi tiết nội dung": content,
            })
        
        for row in s_rows:
            st.markdown(f"- **{row['Phân loại']}:** {row['Chi tiết nội dung']}")


def _render_evidence_panel(evidence: dict, step_key: str = "") -> None:
    """Display extracted evidence with a premium layout, avoiding duplicate fields.

    Args:
        evidence: Dict containing extracted data points.
        step_key: Current workflow node key for conditional rendering.
    """
    with st.expander("📋 Bằng chứng trích xuất từ tài liệu", expanded=False):
        # 1. Unified Formatting for consistency
        def format_val(key, value):
            if value is None:
                return "—"
            if key == "icd_codes" and isinstance(value, list):
                return ", ".join(f"{i.get('code', '')} ({i.get('diagnosis', '')})" if isinstance(i, dict) else str(i) for i in value)
            if key == "medications" and isinstance(value, list):
                return ", ".join(f"{i.get('name', '')} ({i.get('quantity', '')})" if isinstance(i, dict) else str(i) for i in value)
            if isinstance(value, list):
                return ", ".join(str(v) for v in value) if value else "—"
            if isinstance(value, (int, float)) and "amount" in key.lower():
                return f"{value:,.0f} VNĐ"
            return str(value)

        # 2. Key Aliasing & Deduplication Tracking
        # Map multiple possible field names to human-friendly labels
        field_labels = {
            "patient_name": "👤 Họ và tên",
            "policy_number": "🆔 Số hợp đồng",
            "benefit_type": "💡 Loại quyền lợi",
            "treatment_type": "🏥 Hình thức điều trị",
            "treatment_date": "📅 Ngày điều trị",
            "documents_found": "✅ Tài liệu tìm thấy",
            "documents_missing": "❌ Tài liệu thiếu",
            "diagnoses": "🩺 Chẩn đoán",
            "icd_codes": "🔤 Mã ICD",
            "medications": "💊 Danh mục thuốc",
            "total_claim_amount": "💰 Tổng tiền yêu cầu",
            "total_amount": "💰 Tổng tiền yêu cầu", # Alias for deduplication
            "exclusions_found": "🚫 Loại trừ phát hiện",
            "medical_facility": "🏢 Cơ sở y tế",
            "hospital": "🏢 Bệnh viện/Phòng khám",
        }

        # Tracks which keys have already been rendered to prevent duplication
        rendered_keys = set()
        internal_keys = {"history", "data", "is_auto_reviewed", "confidence_score"}

        def render_field(key_list, default_label=None):
            """Render the first available key in key_list and mark all as rendered."""
            for k in key_list:
                if k in evidence and k not in rendered_keys:
                    val = evidence[k]
                    # WHY: If a field exists but is empty/None, we still mark it to avoid fallbacks
                    label = field_labels.get(k, default_label or k.replace("_", " ").title())
                    st.write(f"- **{label}:** {format_val(k, val)}")
                    # Mark all as rendered to prevent duplicates
                    rendered_keys.update(key_list)
                    return True
            return False

        # 3. Step 1 Grouping: General & Documents
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Thông tin chung**")
            render_field(["patient_name"])
            render_field(["policy_number"])
            render_field(["benefit_type"])
            render_field(["treatment_type"])
            render_field(["treatment_date"])

        with col2:
            st.markdown("**Chứng từ**")
            render_field(["documents_found"])
            render_field(["documents_missing"])

        # WHY: For completeness stage, we stop here.
        if step_key == "completeness_check":
            return

        st.divider()

        # Step 2 Grouping: Clinical
        st.markdown("**Thông tin y tế**")
        render_field(["diagnoses"])
        render_field(["icd_codes"])
        render_field(["medications"])

        st.divider()

        # Step 3 Grouping: Financial & Exclusions
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("**Tài chính**")
            # Deduplicate total_claim_amount vs total_amount
            render_field(["total_claim_amount", "total_amount"])

        with col4:
            st.markdown("**Rủi ro & Loại trừ**")
            render_field(["exclusions_found"])

        # 4. Final Cleanup: Render any leftover fields
        leftover_keys = set(evidence.keys()) - rendered_keys - internal_keys
        if leftover_keys:
            st.divider()
            with st.status("📌 Dữ liệu bổ sung khác...", expanded=False):
                for k in sorted(leftover_keys):
                    st.write(f"- **{field_labels.get(k, k.replace('_', ' ').title())}:** {format_val(k, evidence[k])}")


def _render_suggested_updates(
    suggested_updates: list, step_key: str = "unknown", column_labels: Optional[dict] = None
) -> None:
    """Display suggested edits with reference URLs, with dynamic headers for Quality step.

    Args:
        suggested_updates: List of SuggestedUpdate dicts.
        step_key: The workflow step identifier (e.g., 'quality', 'completeness').
        column_labels: Optional mapping of field keys to display column names.
    """
    if not suggested_updates:
        return

    # WHY: Split updates into groups (e.g., ICD vs Medication) to show relevant headers for each.
    groups = {"default": []}
    if step_key == "quality":
        groups = {"icd": [], "medication": []}

    for su in suggested_updates:
        if not isinstance(su, dict):
            continue

        field = str(su.get("field", "")).lower()
        url = str(su.get("reference_url", "")).lower()

        if step_key == "quality":
            # Detection logic for ICD vs Medication
            if "icd" in url or "kcb.vn" in url:
                groups["icd"].append(su)
            else:
                groups["medication"].append(su)
        else:
            groups["default"].append(su)

    # Render each group
    for gtype, items in groups.items():
        if not items:
            continue

        if gtype == "icd":
            labels = {
                "field": "Chẩn đoán",
                "current_value": "ICD trong hồ sơ",
                "suggested_value": "ICD gợi ý",
                "reference_url": "Link tham chiếu",
            }
            title = f"✏️ Gợi ý chỉnh sửa ICD ({len(items)})"
        elif gtype == "medication":
            labels = {
                "field": "Thuốc",
                "current_value": "Chi tiết",
                "suggested_value": "Khuyến nghị",
                "reference_url": "Link tham chiếu",
            }
            title = f"💊 Gợi ý chỉnh sửa Thuốc ({len(items)})"
        else:
            labels = column_labels or {
                "field": "Trường",
                "current_value": "Giá trị hiện tại",
                "suggested_value": "Gợi ý",
                "reference_url": "Link tham chiếu",
            }
            title = f"✏️ Gợi ý chỉnh sửa ({len(items)})"

        with st.expander(title, expanded=True):
            rows = []
            for su in items:
                url = su.get("reference_url") or ""
                rows.append(
                    {
                        labels["field"]: su.get("field", "-"),
                        labels["current_value"]: su.get("current_value") or "—",
                        labels["suggested_value"]: su.get("suggested_value", "-"),
                        labels["reference_url"]: url if url else "—",
                    }
                )

            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        labels["field"]: st.column_config.TextColumn(labels["field"], width="small"),
                        labels["current_value"]: st.column_config.TextColumn(
                            labels["current_value"], width="medium"
                        ),
                        labels["suggested_value"]: st.column_config.TextColumn(
                            labels["suggested_value"], width="medium"
                        ),
                        labels["reference_url"]: st.column_config.LinkColumn(
                            labels["reference_url"], width="small"
                        ),
                    },
                )


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
