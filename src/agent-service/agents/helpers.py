"""Shared utility functions for agent modules."""

from pathlib import Path
from typing import Any

from agents.output_parsing import extract_agent_content, parse_json_response

__all__ = [
    "create_agent_error_state",
    "create_history_entry",
    "extract_called_tools",
    "extract_agent_content",
    "extract_token_usage",
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
    *,
    called_tools: list[str] | None = None,
    token_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create standardized history entry for workflow tracking."""
    entry = {
        "agent": agent_name,
        "prompt": prompt[:200] + "...",
        "result": result,
        "step": step,
    }
    if called_tools:
        entry["called_tools"] = sorted(set(called_tools))
    if token_usage:
        entry["token_usage"] = token_usage
    return entry


def extract_called_tools(agent_result: dict[str, Any]) -> list[str]:
    """Return tool names observed in a LangChain agent response."""
    messages = agent_result.get("messages", []) if isinstance(agent_result, dict) else []
    called: list[str] = []
    for message in messages:
        for tool_call in getattr(message, "tool_calls", []) or []:
            if isinstance(tool_call, dict) and tool_call.get("name"):
                called.append(str(tool_call["name"]))
        tool_name = getattr(message, "name", None)
        message_type = getattr(message, "type", "")
        if tool_name and message_type == "tool":
            called.append(str(tool_name))
    return sorted(set(called))


def extract_token_usage(agent_result: dict[str, Any]) -> dict[str, Any]:
    """Sum provider token metadata across all model calls in an agent response."""
    messages = agent_result.get("messages", []) if isinstance(agent_result, dict) else []
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    llm_call_count = 0

    for message in messages:
        usage = _message_usage_payload(message)
        if not usage:
            continue
        prompt, completion, total = _usage_counts(usage)
        if not any([prompt, completion, total]):
            continue
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total or prompt + completion
        llm_call_count += 1

    if not llm_call_count:
        return {}
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "token_usage": total_tokens,
        "token_usage_source": "provider_metadata",
        "llm_call_count": llm_call_count,
    }


def _message_usage_payload(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage

    response_metadata = getattr(message, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return {}
    for key in ["usage_metadata", "token_usage", "usage"]:
        value = response_metadata.get(key)
        if isinstance(value, dict):
            return value
    return response_metadata


def _usage_counts(usage: dict[str, Any]) -> tuple[int, int, int]:
    prompt_tokens = _first_usage_int(
        usage,
        ["input_tokens", "prompt_tokens", "prompt_token_count", "input_token_count"],
    )
    completion_tokens = _first_usage_int(
        usage,
        [
            "output_tokens",
            "completion_tokens",
            "candidates_token_count",
            "output_token_count",
            "completion_token_count",
        ],
    )
    total_tokens = _first_usage_int(usage, ["total_tokens", "total_token_count"])
    return prompt_tokens, completion_tokens, total_tokens


def _first_usage_int(payload: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return 0


def create_agent_error_state(
    agent_result_key: str,
    error: Exception,
    state: dict[str, Any],
    error_step_name: str,
) -> dict[str, Any]:
    """Create standardized error state for agent nodes."""
    workflow_context = {
        "run_id": state.get("run_id"),
        "claim_id": state.get("claim_id"),
    }
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
                "result": {"error": str(error), **workflow_context},
                "step": error_step_name,
            }
        ],
        "current_step": f"{error_step_name}_error",
        "error": str(error),
    }
