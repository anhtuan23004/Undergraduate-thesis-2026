"""Data models for the Agent Orchestrator."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolType(Enum):
    """Types of tools available to skills."""
    BASH_EXEC = "bash_exec"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    COMPUTER_USE = "computer_use"


@dataclass
class SkillInfo:
    """Metadata about a discovered skill.

    Parsed from SKILL.md YAML frontmatter.
    """
    name: str
    description: str
    path: str  # Path to skill directory
    tools_allowed: List[str] = field(default_factory=list)
    version: str = "1.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Content loaded from SKILL.md
    instructions: str = ""

    @property
    def skill_file_path(self) -> str:
        """Get the full path to SKILL.md."""
        import os
        return os.path.join(self.path, "SKILL.md")


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    exit_code: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Context for skill execution."""
    skill: SkillInfo
    user_input: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    working_directory: str = ""
    env_vars: Dict[str, str] = field(default_factory=dict)

    # Execution tracking
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_tool_call(self, tool_name: str, params: Dict[str, Any], result: ToolResult):
        """Record a tool call."""
        self.tool_calls.append({
            "tool": tool_name,
            "params": params,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })


@dataclass
class ExecutionResult:
    """Result of skill execution."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    tool_calls_count: int = 0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
