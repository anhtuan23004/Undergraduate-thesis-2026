"""Token usage helpers for evaluation runs."""

from __future__ import annotations

from math import ceil
from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate tokens with a conservative four-characters-per-token heuristic."""
    if not text:
        return 0
    return ceil(len(text) / 4)


def token_usage_from_metadata(
    metadata: dict[str, Any] | None,
    prompt_text: str,
    completion_text: str,
) -> dict[str, int | str]:
    """Prefer provider token metadata and fall back to a char-based estimate."""
    metadata = metadata or {}
    usage = _usage_payload(metadata)
    prompt_tokens = _first_int(
        usage,
        ["prompt_tokens", "input_tokens", "prompt_token_count", "input_token_count"],
    )
    completion_tokens = _first_int(
        usage,
        [
            "completion_tokens",
            "output_tokens",
            "completion_token_count",
            "candidates_token_count",
            "output_token_count",
        ],
    )
    total_tokens = _first_int(
        usage,
        ["total_tokens", "total_token_count"],
    )

    if prompt_tokens or completion_tokens or total_tokens:
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "token_usage": total_tokens,
            "token_usage_source": "provider_metadata",
        }

    prompt_tokens = estimate_tokens(prompt_text)
    completion_tokens = estimate_tokens(completion_text)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "token_usage": prompt_tokens + completion_tokens,
        "token_usage_source": "char_estimate",
    }


def _usage_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    for key in ["token_usage", "usage_metadata", "usage"]:
        value = metadata.get(key)
        if isinstance(value, dict):
            return value
    return metadata


def _first_int(payload: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return 0
