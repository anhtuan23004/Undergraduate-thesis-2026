"""Shared utility functions for agent modules.

Provides common functionality for agent nodes to eliminate code duplication.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict


def extract_agent_content(result: dict) -> str:
    """Extract textual content from LangChain agent response.

    Args:
        result: The result dict from agent.invoke().

    Returns:
        The extracted text content as a string.
    """
    messages = result.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    if hasattr(last_message, "content"):
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


def parse_json_response(text: str, default_on_error: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Parse JSON from agent output with markdown cleaning.

    Args:
        text: Raw text from agent response.
        default_on_error: Optional default dict to return if parsing fails.

    Returns:
        Parsed dict or default_on_error if parsing fails.
    """
    if not text:
        if default_on_error:
            return default_on_error
        return {"decision": "reject", "rejection_reason": "No response from agent", "issues_summary": []}

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
    skill_contexts: str = ""
) -> str:
    """Load system prompt from prompts directory by agent name with {{skill_contexts}} substitution.

    Args:
        agent_name: Name of the agent (e.g., "completeness_agent").
        skill_contexts: Combined skill contexts to inject into the prompt.

    Returns:
        The loaded system prompt text with {{skill_contexts}} substituted.
    """
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_path = prompts_dir / f"{agent_name}.md"
    content = prompt_path.read_text(encoding="utf-8")

    # Substitute {{skill_contexts}} placeholder
    if skill_contexts:
        content = content.replace("{{skill_contexts}}", skill_contexts)
    else:
        # Remove empty placeholder if no contexts provided
        content = content.replace("{{skill_contexts}}", "")

    return content


def create_history_entry(
    agent_name: str,
    prompt: str,
    result: Dict[str, Any],
    step: str,
) -> Dict[str, Any]:
    """Create standardized history entry for workflow tracking.

    Args:
        agent_name: Name of the agent.
        prompt: The prompt sent to the agent.
        result: The agent's parsed result.
        step: The workflow step name.

    Returns:
        A history entry dict.
    """
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
    """Create standardized error state for agent nodes.

    Args:
        agent_result_key: The key to use for the agent result in state.
        error: The exception that occurred.
        state: The current workflow state.
        error_step_name: The step name for error tracking.

    Returns:
        A state update dict with error information.
    """
    return {
        agent_result_key: {
            "valid": False,
            "decision": "reject",
            "issues": [{"severity": "critical", "description": f"Error: {str(error)}"}],
        },
        "history": state.get("history", []),
        "current_step": f"{error_step_name}_error",
        "error": str(error),
    }
