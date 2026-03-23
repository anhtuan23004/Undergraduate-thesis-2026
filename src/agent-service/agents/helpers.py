"""Shared utility functions for agent modules.

Provides common functionality for agent nodes to eliminate code duplication.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def extract_agent_content(result: dict) -> str:
    """Extract textual content from LangChain agent response."""
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


def parse_json_response(text: str, default_on_error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Parse JSON from agent output with markdown cleaning."""
    if not text:
        if default_on_error:
            return default_on_error
        return {
            "decision": "reject",
            "rejection_reason": "No response from agent",
            "issues_summary": [],
        }

    cleaned = text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[-1].split("```")[0].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        if default_on_error:
            return default_on_error
        return {
            "decision": "reject",
            "rejection_reason": "Could not parse agent response",
            "issues_summary": [],
        }


def load_system_prompt(
    agent_name: str,
    skill_contexts: str = "",
) -> str:
    """Load system prompt with {{skill_contexts}} substitution."""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_path = prompts_dir / f"{agent_name}.md"
    content = prompt_path.read_text(encoding="utf-8")

    if skill_contexts:
        content = content.replace("{{skill_contexts}}", skill_contexts)
    else:
        content = content.replace("{{skill_contexts}}", "")

    return content


def create_history_entry(
    agent_name: str,
    prompt: str,
    result: Dict[str, Any],
    step: str,
) -> Dict[str, Any]:
    """Create standardized history entry for workflow tracking."""
    return {
        "agent": agent_name,
        "prompt": prompt[:200] + "...",
        "result": result,
        "step": step,
    }


def create_agent_error_state(
    agent_result_key: str,
    error: Exception,
    state: Dict[str, Any],
    error_step_name: str,
) -> Dict[str, Any]:
    """Create standardized error state for agent nodes."""
    return {
        agent_result_key: {
            "valid": False,
            "decision": "reject",
            "issues": [{"severity": "critical", "description": f"Error: {error}"}],
        },
        "history": [
            {"agent": "System", "prompt": "Error generation", "result": {"error": str(error)}, "step": error_step_name}
        ],
        "current_step": f"{error_step_name}_error",
        "error": str(error),
    }
