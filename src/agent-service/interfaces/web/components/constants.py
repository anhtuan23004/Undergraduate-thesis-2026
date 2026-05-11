"""Shared Streamlit UI constants and display labels."""

from __future__ import annotations

from enum import StrEnum


class UIState(StrEnum):
    """Primary UI states used by the app."""

    PROCESSING = "processing"
    WAITING_FOR_HUMAN = "waiting_for_human"
    ERROR = "error"
    COMPLETED = "completed"


class HITLDecision(StrEnum):
    """Human-in-the-loop decision values sent to API."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class StepStatus(StrEnum):
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
    "ocr_extraction": "Trích xuất OCR chi tiết",
    "agent_review": "Duyệt tự động",
    "quality": "Kiểm tra chất lượng",
    "human_review": "Thẩm định thủ công",
    "final_decision": "Kết luận cuối cùng",
}

STEP_TITLES = {
    "completeness": "Bước 1 - Kiểm tra tính đầy đủ",
    "agent_review": "Bước 2 - Duyệt tự động (Agent Review)",
    "quality": "Bước 3 - Kiểm tra chất lượng y tế",
    "human_review": "Bước 4 - Kết quả thẩm định thủ công",
    "final_decision": "Bước 5 - Kết luận cuối cùng",
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

HITL_DECISION_LABELS = {
    HITLDecision.APPROVE.value: "Phê duyệt",
    HITLDecision.REJECT.value: "Từ chối",
    HITLDecision.EDIT.value: "Chỉnh sửa",
}

HISTORY_STATE_EMOJIS = {
    UIState.PROCESSING: "🟦",
    UIState.WAITING_FOR_HUMAN: "🟨",
    UIState.ERROR: "🟥",
    UIState.COMPLETED: "🟩",
}

FRIENDLY_STEP_NAMES = {
    "completeness_agent": "Kiểm tra tính đầy đủ",
    "quality_agent": "Kiểm tra chất lượng y tế",
    "decision_agent": "Kết luận cuối cùng",
    "human_review": "Thẩm định thủ công",
    "human_review_complete": "Hoàn tất thẩm định thủ công",
    "manual_continue": "Tiếp tục thủ công",
    "agent_review": "Duyệt tự động (Agent Review)",
    "verifier_agent": "Xác minh chéo (Verifier)",
}
