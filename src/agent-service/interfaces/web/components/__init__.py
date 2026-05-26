"""Streamlit UI components for insurance claims workflow monitoring and review."""

from __future__ import annotations

from importlib import import_module

from .constants import (
    BADGE_BY_STEP_STATUS,
    HITL_DECISION_LABELS,
    SEVERITY_COLORS,
    STEP_ICONS,
    STEP_LABELS,
    STEP_ORDER,
    STEP_TITLES,
    HITLDecision,
    StepStatus,
    UIState,
)
from .formatters import (
    _friendly_decision,
    _friendly_status,
    _friendly_step_name,
    format_history_label,
    friendly_decision,
    friendly_status,
    friendly_step_name,
)
from .timeline_state import _compute_timeline_status, compute_timeline_status, get_ui_state

_LAZY_EXPORTS = {
    "render_error_state": (".errors", "render_error_state"),
    "render_document_tab_link": (".document_view", "render_document_tab_link"),
    "workflow_document_url": (".document_view", "workflow_document_url"),
    "render_final_dashboard": (".final_dashboard", "render_final_dashboard"),
    "_render_confidence_badge": (".findings", "_render_confidence_badge"),
    "_render_evidence_panel": (".findings", "_render_evidence_panel"),
    "_render_issue_details": (".findings", "_render_issue_details"),
    "_render_medical_findings": (".findings", "_render_medical_findings"),
    "_render_suggested_updates": (".findings", "_render_suggested_updates"),
    "render_confidence_badge": (".findings", "render_confidence_badge"),
    "render_evidence_panel": (".findings", "render_evidence_panel"),
    "render_issue_details": (".findings", "render_issue_details"),
    "render_medical_findings": (".findings", "render_medical_findings"),
    "render_suggested_updates": (".findings", "render_suggested_updates"),
    "render_history_log": (".history", "render_history_log"),
    "_get_pending_assessment": (".review_panel", "_get_pending_assessment"),
    "_get_editable_assessment": (".review_panel", "_get_editable_assessment"),
    "_render_agent_review_summary": (".review_panel", "_render_agent_review_summary"),
    "_render_assessment_findings": (".review_panel", "_render_assessment_findings"),
    "get_pending_assessment": (".review_panel", "get_pending_assessment"),
    "get_editable_assessment": (".review_panel", "get_editable_assessment"),
    "render_agent_review_summary": (".review_panel", "render_agent_review_summary"),
    "render_assessment_findings": (".review_panel", "render_assessment_findings"),
    "render_human_review_panel": (".review_panel", "render_human_review_panel"),
    "render_brand_theme": (".theme", "render_brand_theme"),
    "render_app_header": (".timeline", "render_app_header"),
    "render_claim_submission": (".timeline", "render_claim_submission"),
    "render_monitoring": (".timeline", "render_monitoring"),
    "render_raw_state": (".timeline", "render_raw_state"),
    "render_sidebar": (".timeline", "render_sidebar"),
    "render_step_messages": (".timeline", "render_step_messages"),
    "render_timeline": (".timeline", "render_timeline"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


__all__ = [
    "BADGE_BY_STEP_STATUS",
    "HITLDecision",
    "HITL_DECISION_LABELS",
    "SEVERITY_COLORS",
    "STEP_ICONS",
    "STEP_LABELS",
    "STEP_ORDER",
    "STEP_TITLES",
    "StepStatus",
    "UIState",
    "_compute_timeline_status",
    "_friendly_status",
    "_friendly_decision",
    "_friendly_step_name",
    "_get_pending_assessment",
    "_get_editable_assessment",
    "_render_agent_review_summary",
    "_render_assessment_findings",
    "_render_confidence_badge",
    "_render_evidence_panel",
    "_render_issue_details",
    "_render_medical_findings",
    "_render_suggested_updates",
    "compute_timeline_status",
    "format_history_label",
    "friendly_status",
    "friendly_decision",
    "friendly_step_name",
    "get_pending_assessment",
    "get_editable_assessment",
    "get_ui_state",
    "render_agent_review_summary",
    "render_app_header",
    "render_assessment_findings",
    "render_brand_theme",
    "render_claim_submission",
    "render_confidence_badge",
    "render_document_tab_link",
    "render_error_state",
    "render_evidence_panel",
    "render_final_dashboard",
    "render_history_log",
    "render_human_review_panel",
    "render_issue_details",
    "render_medical_findings",
    "render_monitoring",
    "render_raw_state",
    "render_sidebar",
    "render_step_messages",
    "render_suggested_updates",
    "render_timeline",
    "workflow_document_url",
]
