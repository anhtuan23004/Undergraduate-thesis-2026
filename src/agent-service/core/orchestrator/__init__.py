"""AI Agent Orchestrator with Skill Discovery and Execution.

A Claude Agent Skills-inspired system using LangGraph for orchestration.

Usage:
    from core.orchestrator import AgentOrchestrator, SkillDiscovery

    # Create orchestrator
    orchestrator = AgentOrchestrator()

    # Discover skills
    skills = await orchestrator.discover_skills()

    # Process a request
    result = await orchestrator.process("Search for Python tutorials")

    # Or use specific skill
    result = await orchestrator.process(
        "Search for Python tutorials",
        skill_name="web_search"
    )
"""
from core.orchestrator.discovery import SkillDiscovery
from core.orchestrator.models import (
    ExecutionContext,
    ExecutionResult,
    SkillInfo,
    ToolResult,
)
from core.orchestrator.orchestrator import AgentOrchestrator, OrchestratorConfig
from core.orchestrator.tools import ToolRegistry, ToolType

__all__ = [
    # Main orchestrator
    "AgentOrchestrator",
    "OrchestratorConfig",

    # Discovery
    "SkillDiscovery",

    # Models
    "SkillInfo",
    "ExecutionContext",
    "ExecutionResult",
    "ToolResult",

    # Tools
    "ToolRegistry",
    "ToolType",
]
