"""Result normalization and presentation helpers for Streamlit UI."""

from typing import Any, Dict, List, Optional


def normalize_agent_result(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize raw agent output into display schema."""
    if not raw:
        return {}

    if "decision" in raw:
        decision = str(raw["decision"])
    elif "valid" in raw:
        decision = "accept" if raw["valid"] else "reject"
    else:
        decision = "unknown"

    confidence = raw.get("confidence", 0.0)
    if isinstance(confidence, str):
        confidence = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(
            confidence.lower(), 0.5
        )
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    reasoning = raw.get("reasoning") or raw.get("reason", "")
    if not reasoning:
        for block in raw.get("analysis", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                reasoning = block["text"]
                break

    issues: List[Dict[str, Any]] = []
    for issue in raw.get("issues", []) or []:
        if isinstance(issue, dict):
            issues.append(
                {
                    "severity": issue.get("severity", "medium"),
                    "description": issue.get("description") or issue.get("message", ""),
                    "field": issue.get("field", ""),
                }
            )

    missing_docs = raw.get("missing_documents", []) or []
    doc_check = raw.get("document_check") or {}
    if not missing_docs and doc_check:
        mandatory = doc_check.get("mandatory_documents", {}) or {}
        missing_docs = [
            item.get("name", item.get("type", str(item)))
            for item in mandatory.get("missing", []) or []
        ]

    return {
        "decision": decision,
        "confidence": confidence,
        "reasoning": reasoning,
        "issues": issues,
        "missing_documents": missing_docs,
    }


def get_decision_color(decision: str) -> str:
    """Get color hex for a final decision."""
    decision_upper = decision.upper()
    if decision_upper in {"APPROVE", "ACCEPT"}:
        return "#28a745"
    if decision_upper == "REJECT":
        return "#dc3545"
    if decision_upper == "PENDING":
        return "#ffc107"
    return "#6c757d"


def get_decision_emoji(decision: str) -> str:
    """Get emoji for a final decision."""
    decision_upper = decision.upper()
    if decision_upper in {"APPROVE", "ACCEPT"}:
        return "✅"
    if decision_upper == "REJECT":
        return "❌"
    if decision_upper == "PENDING":
        return "⏳"
    return "❓"
