"""Pure display formatter helpers for the Streamlit UI."""

from __future__ import annotations

from typing import Any

from .constants import FRIENDLY_STEP_NAMES, HISTORY_STATE_EMOJIS


def format_history_label(runs: list[dict], run_id: str, state_getter) -> str:
    """Format a run selector option label."""
    run = next((item for item in runs if item.get("run_id") == run_id), {})
    state = state_getter(run.get("data"))
    emoji = HISTORY_STATE_EMOJIS.get(state, "⬜")
    claim = run.get("claim_id", "-")
    return f"{emoji} {run_id[:8]} | {claim}"


def friendly_step_name(step_raw: str) -> str:
    """Map technical workflow step names to reviewer-facing Vietnamese labels."""
    raw = step_raw.lower()
    if raw in FRIENDLY_STEP_NAMES:
        return FRIENDLY_STEP_NAMES[raw]

    if "agent_review" in raw or "verifier" in raw:
        return "Duyệt tự động"
    if "completeness" in raw:
        return "Kiểm tra tính đầy đủ"
    if "quality" in raw:
        return "Kiểm tra chất lượng y tế"
    if "human_review" in raw or "human" in raw:
        return "Thẩm định thủ công"
    if "final" in raw or "decision" in raw:
        return "Kết luận cuối cùng"
    if "start" in raw:
        return "Khởi tạo quy trình"
    return step_raw


def friendly_status(decision: Any, result: dict) -> str:
    """Map raw decision/status values to reviewer-facing labels."""
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


def friendly_decision(decision: Any) -> str:
    """Map raw decision values to Vietnamese display labels."""
    decision_text = str(decision).lower()
    if decision_text in ("approve", "accept", "accepted"):
        return "Phê duyệt"
    if decision_text in ("reject", "rejected"):
        return "Từ chối"
    if decision_text in ("accept_with_edit", "edit"):
        return "Cần chỉnh sửa"
    if decision in (None, ""):
        return "-"
    if decision == "-":
        return "-"
    return str(decision)


_friendly_step_name = friendly_step_name
_friendly_status = friendly_status
_friendly_decision = friendly_decision
