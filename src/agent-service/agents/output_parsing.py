"""Agent output extraction and JSON parsing helpers."""

import json
from typing import Any


def extract_agent_content(result: dict[str, Any]) -> str:
    """Extract textual content from a LangChain agent response."""
    messages = result.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    if not hasattr(last_message, "content"):
        return str(last_message).strip()

    content = last_message.content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()

    if isinstance(content, str):
        return content.strip()

    return str(last_message).strip()


def parse_json_response(
    text: str,
    default_on_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse JSON from agent output with markdown fence cleanup."""
    if not text:
        return default_on_error or _default_parse_error("No response from agent")

    try:
        return json.loads(_strip_json_fence(text))
    except json.JSONDecodeError:
        return default_on_error or _default_parse_error("Could not parse agent response")


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if "```json" in cleaned:
        return cleaned.split("```json")[-1].split("```")[0].strip()
    if cleaned.startswith("```"):
        return cleaned.strip("`").strip()
    return cleaned


def _default_parse_error(reason: str) -> dict[str, Any]:
    return {
        "decision": "reject",
        "rejection_reason": reason,
        "issues_summary": [],
    }
