"""Utilities for reviewing and updating manual evaluation labels."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from eval.schemas import DEFAULT_EXPECTED_TOOLS, normalize_final_decision

DECISION_OPTIONS = ["", "accept", "reject", "needs_review"]
LABEL_STATUS_OPTIONS = ["unlabeled", "reviewed", "final"]
COMPLEXITY_OPTIONS = ["simple", "ambiguous", "complex"]
ROUTING_NODE_OPTIONS = [
    "completeness_check",
    "quality_check",
    "final_decision",
    "agent_review",
    "human_review",
]
COMMON_MISSING_DOCS = [
    "claim_form",
    "invoice",
    "receipt",
    "medical_report",
    "prescription",
    "discharge_summary",
    "accident_report",
    "id_document",
]
COMMON_EXCLUSIONS = [
    "cosmetic_treatment",
    "pre_existing_condition",
    "waiting_period",
    "non_covered_medication",
    "out_of_policy_period",
]
COMMON_QUALITY_ISSUES = [
    "missing_required_document",
    "icd_missing",
    "icd_mismatch",
    "excluded_diagnosis",
    "medicine_mismatch",
    "inconsistent_patient_name",
    "inconsistent_treatment_date",
    "inconsistent_amount",
    "poor_ocr_quality",
]


def load_dataset(path: Path) -> dict[str, Any]:
    """Load a ground-truth dataset JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomically save JSON to avoid partial writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        tmp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    tmp_path.replace(path)


def get_claims(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Return claims from a dataset payload."""
    claims = dataset.get("claims", [])
    return claims if isinstance(claims, list) else []


def label_progress(claims: list[dict[str, Any]]) -> dict[str, int]:
    """Count labels by status."""
    counts = dict.fromkeys(LABEL_STATUS_OPTIONS, 0)
    for claim in claims:
        status = claim.get("label_status", "unlabeled")
        counts[status if status in counts else "unlabeled"] += 1
    counts["total"] = len(claims)
    return counts


def filter_claims(
    claims: list[dict[str, Any]],
    status: str = "all",
    category_code: str = "all",
    query: str = "",
) -> list[dict[str, Any]]:
    """Filter claims for reviewer navigation."""
    query = query.strip().lower()
    filtered = []
    for claim in claims:
        if status != "all" and claim.get("label_status", "unlabeled") != status:
            continue
        if category_code != "all" and claim.get("category_code") != category_code:
            continue
        haystack = " ".join(
            str(claim.get(field, ""))
            for field in ["claim_id", "file_name", "patient_name", "category_code"]
        ).lower()
        if query and query not in haystack:
            continue
        filtered.append(claim)
    return filtered


def claim_label_fields(claim: dict[str, Any]) -> dict[str, Any]:
    """Return only fields edited by the labeling UI."""
    return {
        "expected_decision": claim.get("expected_decision", ""),
        "expected_missing_docs": claim.get("expected_missing_docs", []),
        "expected_icd_codes": claim.get("expected_icd_codes", []),
        "expected_exclusions": claim.get("expected_exclusions", []),
        "expected_quality_issues": claim.get("expected_quality_issues", []),
        "expected_routing_path": claim.get("expected_routing_path", []),
        "expected_tools_by_agent": claim.get("expected_tools_by_agent", DEFAULT_EXPECTED_TOOLS),
        "complexity": claim.get("complexity", "simple"),
        "label_status": claim.get("label_status", "unlabeled"),
        "expert_notes": claim.get("expert_notes", ""),
    }


def load_agent_suggestions(path: Path) -> dict[str, dict[str, Any]]:
    """Load agent-assisted labeling suggestions keyed by claim id."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("suggestions", [])
    suggestions: dict[str, dict[str, Any]] = {}
    for row in rows:
        claim_id = row.get("claim_id")
        if claim_id:
            suggestions[str(claim_id)] = row
    return suggestions


def load_reviewed_labels(path: Path) -> dict[str, dict[str, Any]]:
    """Load reviewer labels keyed by claim id."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("labels", [])
    labels: dict[str, dict[str, Any]] = {}
    for row in rows:
        claim_id = row.get("claim_id")
        if claim_id:
            labels[str(claim_id)] = row
    return labels


def save_reviewed_label(
    path: Path, claim: dict[str, Any], updates: dict[str, Any]
) -> dict[str, Any]:
    """Save one reviewed label without mutating the dataset source."""
    labels = load_reviewed_labels(path)
    claim_id = str(claim.get("claim_id", ""))
    reviewed = {
        "claim_id": claim_id,
        "file_name": claim.get("file_name", ""),
        "file_path": claim.get("file_path", ""),
        "category_code": claim.get("category_code", ""),
        **updates,
    }
    labels[claim_id] = reviewed
    payload = {"labels": [labels[key] for key in sorted(labels)]}
    save_json_atomic(path, payload)
    return reviewed


def suggestion_to_label_updates(suggestion: dict[str, Any]) -> dict[str, Any]:
    """Convert an agent suggestion record into editable label fields."""
    updates = {
        "expected_decision": normalize_final_decision(suggestion.get("final_decision")),
        "expected_missing_docs": _string_list(suggestion.get("missing_docs", [])),
        "expected_icd_codes": _string_list(suggestion.get("icd_codes", [])),
        "expected_exclusions": _string_list(suggestion.get("exclusions", [])),
        "expected_quality_issues": _string_list(suggestion.get("quality_issues", [])),
        "expected_routing_path": _string_list(suggestion.get("routing_path", [])),
        "expected_tools_by_agent": suggestion.get("called_tools_by_agent")
        or DEFAULT_EXPECTED_TOOLS,
    }
    if suggestion.get("complexity"):
        updates["complexity"] = str(suggestion["complexity"])
    return updates


def label_draft_for_claim(
    claim: dict[str, Any],
    suggestion: dict[str, Any] | None,
    reviewed_label: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the editable label draft for a claim."""
    if reviewed_label:
        return claim_label_fields(reviewed_label)
    if suggestion:
        draft = claim_label_fields({})
        draft.update(suggestion_to_label_updates(suggestion))
        draft["label_status"] = "reviewed"
        draft["expert_notes"] = "Agent-assisted draft. Reviewer must verify against the source PDF."
        return draft
    return claim_label_fields(claim)


def parse_lines(value: str) -> list[str]:
    """Parse newline/comma-separated reviewer input into unique ordered strings."""
    items: list[str] = []
    for line in value.replace(",", "\n").splitlines():
        item = line.strip()
        if item and item not in items:
            items.append(item)
    return items


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def list_to_lines(values: list[str]) -> str:
    """Render list values as one item per line."""
    return "\n".join(str(value) for value in values)


def parse_tools_json(value: str) -> dict[str, list[str]]:
    """Parse expected tools JSON from the labeling UI."""
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("expected_tools_by_agent must be a JSON object")
    normalized: dict[str, list[str]] = {}
    for agent, tools in parsed.items():
        if not isinstance(tools, list):
            raise ValueError(f"Tool list for {agent} must be an array")
        normalized[str(agent)] = [str(tool) for tool in tools]
    return normalized


def validate_claim_label(claim: dict[str, Any]) -> list[str]:
    """Validate label fields. Final labels are intentionally strict."""
    errors: list[str] = []
    decision = normalize_final_decision(claim.get("expected_decision"))
    status = claim.get("label_status", "unlabeled")

    errors.extend(_validate_scalar_fields(claim, decision, status))
    errors.extend(_validate_list_fields(claim))
    errors.extend(_validate_tools(claim))

    if status == "final":
        errors.extend(_validate_final_requirements(claim, decision))

    return errors


def _validate_scalar_fields(claim: dict[str, Any], decision: str, status: str) -> list[str]:
    errors: list[str] = []
    if decision and decision not in DECISION_OPTIONS:
        errors.append("expected_decision must be accept, reject, or needs_review.")
    if status not in LABEL_STATUS_OPTIONS:
        errors.append("label_status must be unlabeled, reviewed, or final.")
    if claim.get("complexity") and claim.get("complexity") not in COMPLEXITY_OPTIONS:
        errors.append("complexity must be simple, ambiguous, or complex.")
    return errors


def _validate_list_fields(claim: dict[str, Any]) -> list[str]:
    list_fields = [
        "expected_missing_docs",
        "expected_icd_codes",
        "expected_exclusions",
        "expected_quality_issues",
        "expected_routing_path",
    ]
    return [
        f"{field} must be a list."
        for field in list_fields
        if not isinstance(claim.get(field, []), list)
    ]


def _validate_tools(claim: dict[str, Any]) -> list[str]:
    tools = claim.get("expected_tools_by_agent", {})
    if not isinstance(tools, dict):
        return ["expected_tools_by_agent must be an object."]
    if any(not isinstance(value, list) for value in tools.values()):
        return ["Every expected_tools_by_agent value must be a list."]
    return []


def _validate_final_requirements(claim: dict[str, Any], decision: str) -> list[str]:
    errors: list[str] = []
    if decision not in {"accept", "reject", "needs_review"}:
        errors.append("Final labels require expected_decision.")
    if not claim.get("expected_routing_path"):
        errors.append("Final labels require expected_routing_path.")
    if not claim.get("expert_notes", "").strip():
        errors.append("Final labels require expert_notes for auditability.")
    return errors
