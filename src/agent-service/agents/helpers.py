"""Shared utility functions for agent modules."""

from pathlib import Path
from typing import Any

from agents.output_parsing import extract_agent_content, parse_json_response

__all__ = [
    "create_agent_error_state",
    "create_history_entry",
    "extract_agent_content",
    "load_system_prompt",
    "parse_json_response",
]


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
    result: dict[str, Any],
    step: str,
) -> dict[str, Any]:
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
    state: dict[str, Any],
    error_step_name: str,
) -> dict[str, Any]:
    """Create standardized error state for agent nodes."""
    return {
        agent_result_key: {
            "valid": False,
            "decision": "reject",
            "issues": [{"severity": "critical", "description": f"Error: {error}"}],
        },
        "history": [
            {
                "agent": "System",
                "prompt": "Error generation",
                "result": {"error": str(error)},
                "step": error_step_name,
            }
        ],
        "current_step": f"{error_step_name}_error",
        "error": str(error),
    }
