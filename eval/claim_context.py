"""Shared claim metadata normalization for evaluation prompts."""

from __future__ import annotations

from typing import Any


def build_claim_context(
    claim: dict[str, Any],
    *,
    include_policy_number: bool = False,
) -> dict[str, Any]:
    """Return the stable claim metadata block used in LLM prompts."""
    context = {
        "claim_id": claim.get("claim_id", ""),
        "file_name": claim.get("file_name", ""),
        "file_path": claim.get("file_path", ""),
        "category_code": claim.get("category_code", ""),
    }
    if include_policy_number:
        context["policy_number"] = claim.get("policy_number") or claim.get("policy_id") or ""
    return context
