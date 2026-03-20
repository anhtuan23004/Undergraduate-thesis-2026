"""Dynamic skill and tool loader for agent-based architecture.

This module provides runtime discovery and loading of tools and their associated
skill contexts organized by agent type. It supports both LangChain @tool decorated
functions and BaseTool subclasses, with automatic kebab-case to snake_case mapping.
"""

import importlib.util
import json
import logging
import os
import structlog
import sys
import types
import typing
from pathlib import Path
from typing import Dict, List, Tuple

from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.tools.structured import StructuredTool

logger = structlog.get_logger()

# Module-level cache for loaded skills to avoid repeated file I/O
_skill_cache: Dict[str, Tuple[List[LangChainBaseTool], str]] = {}

# Strict mode for testing - fail on import errors
STRICT_SKILL_LOADING = os.getenv("STRICT_SKILL_LOADING", "false").lower() == "true"


def _snake_to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case.

    Args:
        name: snake_case string

    Returns:
        kebab-case string
    """
    return name.replace("_", "-")


def _kebab_to_snake(name: str) -> str:
    """Convert kebab-case to snake_case.

    Args:
        name: kebab-case string

    Returns:
        snake_case string
    """
    return name.replace("-", "_")


def _read_skill_content(skill_dir: Path) -> str:
    """Read SKILL.md content without YAML frontmatter.

    Args:
        skill_dir: Path to skill directory containing SKILL.md

    Returns:
        SKILL.md content without frontmatter, or empty string if not found
    """
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return ""

    content = skill_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Skip YAML frontmatter (content between first and second "---")
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                # Return everything after frontmatter
                return "\n".join(lines[i + 1 :]).strip()

    return content.strip()


def _import_tool_from_module(
    skill_dir: Path, tool_name: str
) -> LangChainBaseTool | None:
    """Import a tool function from a skill's scripts/tool.py.

    Args:
        skill_dir: Path to skill directory
        tool_name: Name of the tool function (kebab-case from directory name)

    Returns:
        LangChain tool or None if import fails
    """
    tool_file = skill_dir / "scripts" / "tool.py"
    if not tool_file.exists():
        logger.warning(f"Tool file not found: {tool_file}")
        return None

    # Build module name from path: skills.quality_agent.validate_medication
    relative_path = skill_dir.relative_to(skill_dir.parent.parent)
    module_parts = list(relative_path.parts)
    module_parts = [_kebab_to_snake(p) for p in module_parts]
    module_name = ".".join(module_parts) + ".scripts.tool"

    try:
        # Dynamic import
        spec = importlib.util.spec_from_file_location(module_name, tool_file)
        if spec is None or spec.loader is None:
            logger.warning(f"Could not create module spec for: {tool_file}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys_modules_key = f"{module_name}_skills"
        import sys

        sys.modules[sys_modules_key] = module
        spec.loader.exec_module(module)

        # Find @tool decorated function
        for attr_name in dir(module):
            # Skip private attributes and module-level imports
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)

            # Skip typing module objects, modules, and built-in types
            if isinstance(
                attr,
                (
                    typing._SpecialGenericAlias,
                    typing._SpecialForm,
                    types.ModuleType,
                    type,
                ),
            ):
                continue

            # Check if it's a LangChain tool first (StructuredTool is not callable)
            if isinstance(attr, (StructuredTool, LangChainBaseTool)):
                logger.debug(f"Found LangChain tool: {attr_name}")
                return attr

        logger.warning(f"No @tool found in: {tool_file}")
        return None

    except Exception as e:
        error_msg = f"Failed to import tool from {tool_file}: {e}"
        if STRICT_SKILL_LOADING:
            raise ImportError(error_msg) from e
        logger.error(error_msg, exc_info=True)
        return None


def load_agent_skills(agent_name: str) -> Tuple[List[LangChainBaseTool], str]:
    """Load all tools and skill contexts for a specific agent.

    Scans skills/{agent_name}/ and skills/shared/ directories.
    Returns: (list of LangChain tools, combined skill_contexts string)

    Args:
        agent_name: Agent name in snake_case (e.g., "quality_agent")

    Returns:
        Tuple of (tools list, combined skill contexts string)
    """
    # Check cache first
    if agent_name in _skill_cache:
        return _skill_cache[agent_name]

    skills_dir = Path(__file__).parent.parent / "skills"
    agent_dir = skills_dir / _snake_to_kebab(agent_name)
    shared_dir = skills_dir / "shared"

    tools: List[LangChainBaseTool] = []
    skill_contexts_parts: List[str] = []

    # Load agent-specific skills
    if agent_dir.exists() and agent_dir.is_dir():
        for skill_dir in sorted(agent_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            tool = _import_tool_from_module(skill_dir, skill_dir.name)
            if tool:
                tools.append(tool)
                skill_content = _read_skill_content(skill_dir)
                if skill_content:
                    # Add with H3 heading for clarity
                    skill_contexts_parts.append(
                        f"### Available Tool: {skill_dir.name}\n{skill_content}"
                    )
    else:
        logger.warning(f"Agent skill directory not found: {agent_dir}")

    # Load shared skills
    if shared_dir.exists() and shared_dir.is_dir():
        for skill_dir in sorted(shared_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            tool = _import_tool_from_module(skill_dir, skill_dir.name)
            if tool:
                tools.append(tool)
                skill_content = _read_skill_content(skill_dir)
                if skill_content:
                    skill_contexts_parts.append(
                        f"### Available Tool: {skill_dir.name}\n{skill_content}"
                    )

    combined_contexts = "\n\n".join(skill_contexts_parts)

    # Cache the result
    _skill_cache[agent_name] = (tools, combined_contexts)

    logger.info(
        f"Loaded {len(tools)} tools for agent '{agent_name}'",
        tool_names=[t.name if hasattr(t, "name") else str(t) for t in tools],
    )

    return tools, combined_contexts


def clear_skill_cache() -> None:
    """Clear the skill cache for testing purposes."""
    global _skill_cache
    _skill_cache = {}
    logger.info("Skill cache cleared")


__all__ = ["load_agent_skills", "clear_skill_cache"]
