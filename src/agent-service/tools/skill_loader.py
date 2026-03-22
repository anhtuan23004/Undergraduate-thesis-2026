"""Dynamic skill and tool loader for agent-based architecture.

This module provides runtime discovery and loading of tools and their associated
skill contexts organized by agent type. It supports both LangChain @tool decorated
functions and BaseTool subclasses, with automatic kebab-case to snake_case mapping.
"""

import importlib.util
import json
import os
import structlog
import sys
import types
import typing
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.tools.structured import StructuredTool

logger = structlog.get_logger()

# Module-level cache for loaded skills to avoid repeated file I/O
_skill_cache: Dict[str, Tuple[List[LangChainBaseTool], str]] = {}

# Strict mode for testing - fail on import errors
STRICT_SKILL_LOADING = os.getenv("STRICT_SKILL_LOADING", "false").lower() == "true"


def _snake_to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case."""
    return name.replace("_", "-")


def _kebab_to_snake(name: str) -> str:
    """Convert kebab-case to snake_case."""
    return name.replace("-", "_")


def _read_skill_content(skill_dir: Path) -> str:
    """Read SKILL.md content without YAML frontmatter."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return ""

    content = skill_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Skip YAML frontmatter (content between first and second "---")
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()

    return content.strip()


def _get_module_name_from_path(skill_dir: Path) -> str:
    """Generate a unique module name from the skill path."""
    relative_path = skill_dir.relative_to(skill_dir.parent.parent)
    module_parts = [_kebab_to_snake(p) for p in relative_path.parts]
    return ".".join(module_parts) + ".scripts.tool"


def _find_tool_in_module(module: types.ModuleType) -> Optional[LangChainBaseTool]:
    """Search for a LangChain tool in an imported module."""
    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue

        attr = getattr(module, attr_name)

        # Skip typing, modules, and built-in types
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

        # Check for LangChain tool types
        if isinstance(attr, (StructuredTool, LangChainBaseTool)):
            logger.debug(f"Found LangChain tool: {attr_name}")
            return attr
    return None


def _import_tool_from_module(skill_dir: Path, tool_name: str) -> Optional[LangChainBaseTool]:
    """Import a tool function from a skill's scripts/tool.py."""
    tool_file = skill_dir / "scripts" / "tool.py"
    if not tool_file.exists():
        logger.warning(f"Tool file not found: {tool_file}")
        return None

    module_name = _get_module_name_from_path(skill_dir)

    try:
        spec = importlib.util.spec_from_file_location(module_name, tool_file)
        if spec is None or spec.loader is None:
            logger.warning(f"Could not create module spec: {tool_file}")
            return None

        module = importlib.util.module_from_spec(spec)
        # Use a unique key in sys.modules to avoid collisions
        sys.modules[f"{module_name}_skills"] = module
        spec.loader.exec_module(module)

        tool = _find_tool_in_module(module)
        if tool:
            return tool

        logger.warning(f"No @tool found in: {tool_file}")
        return None

    except Exception as e:
        error_msg = f"Failed to import tool from {tool_file}: {e}"
        if STRICT_SKILL_LOADING:
            raise ImportError(error_msg) from e
        logger.error(error_msg, exc_info=True)
        return None


def _load_skills_recursive(
    search_dir: Path, tools: List[LangChainBaseTool], contexts: List[str]
) -> None:
    """Helper to load skills from a given directory."""
    if not (search_dir.exists() and search_dir.is_dir()):
        return

    for skill_dir in sorted(search_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        tool = _import_tool_from_module(skill_dir, skill_dir.name)
        if tool:
            tools.append(tool)
            content = _read_skill_content(skill_dir)
            if content:
                contexts.append(f"### Available Tool: {skill_dir.name}\n{content}")


def load_agent_skills(agent_name: str) -> Tuple[List[LangChainBaseTool], str]:
    """Load all tools and skill contexts for a specific agent."""
    if agent_name in _skill_cache:
        return _skill_cache[agent_name]

    skills_root = Path(__file__).parent.parent / "skills"
    agent_dir = skills_root / _snake_to_kebab(agent_name)
    shared_dir = skills_root / "shared"

    tools: List[LangChainBaseTool] = []
    skill_contexts_parts: List[str] = []

    # Load specific and shared skills
    _load_skills_recursive(agent_dir, tools, skill_contexts_parts)
    _load_skills_recursive(shared_dir, tools, skill_contexts_parts)

    combined_contexts = "\n\n".join(skill_contexts_parts)
    _skill_cache[agent_name] = (tools, combined_contexts)

    logger.info(
        f"Loaded {len(tools)} tools for agent '{agent_name}'",
        tool_names=[t.name if hasattr(t, "name") else str(t) for t in tools],
    )

    return tools, combined_contexts


def clear_skill_cache() -> None:
    """Clear the skill cache."""
    global _skill_cache
    _skill_cache = {}
    logger.info("Skill cache cleared")


__all__ = ["load_agent_skills", "clear_skill_cache"]
