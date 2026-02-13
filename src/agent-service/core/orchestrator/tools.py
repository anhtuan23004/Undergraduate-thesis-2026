"""Tool implementations for skill execution.

Provides tools that skills can use:
- bash_exec: Execute bash commands and scripts
- file_read: Read file contents
- file_write: Write content to files
- computer_use: Simulate cursor/keyboard interactions
"""
import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from pydantic import BaseModel, Field

from core.orchestrator.models import ToolResult, ToolType

logger = structlog.get_logger()


class BashExecInput(BaseModel):
    """Input schema for bash_exec tool."""
    command: str = Field(description="Bash command to execute")
    working_dir: Optional[str] = Field(None, description="Working directory")
    timeout: int = Field(30, description="Timeout in seconds")
    env_vars: Optional[Dict[str, str]] = Field(None, description="Environment variables")


class FileReadInput(BaseModel):
    """Input schema for file_read tool."""
    path: str = Field(description="File path to read")
    limit: Optional[int] = Field(None, description="Max lines to read")


class FileWriteInput(BaseModel):
    """Input schema for file_write tool."""
    path: str = Field(description="File path to write")
    content: str = Field(description="Content to write")
    append: bool = Field(False, description="Append to file instead of overwrite")


class ComputerUseInput(BaseModel):
    """Input schema for computer_use tool."""
    action: str = Field(description="Action: type, click, press, screenshot")
    text: Optional[str] = Field(None, description="Text to type")
    x: Optional[int] = Field(None, description="X coordinate for click")
    y: Optional[int] = Field(None, description="Y coordinate for click")
    key: Optional[str] = Field(None, description="Key to press")


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self, allowed_tools: Optional[list] = None):
        """Initialize tool registry.

        Args:
            allowed_tools: List of allowed tool names (None = all allowed)
        """
        self.allowed_tools = set(allowed_tools) if allowed_tools else None
        self._tools: Dict[str, callable] = {
            ToolType.BASH_EXEC.value: self.bash_exec,
            ToolType.FILE_READ.value: self.file_read,
            ToolType.FILE_WRITE.value: self.file_write,
            ToolType.COMPUTER_USE.value: self.computer_use,
        }
        self.logger = logger.bind(component="tool_registry")

    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed."""
        if self.allowed_tools is None:
            return True
        return tool_name in self.allowed_tools

    def get_tool(self, name: str) -> Optional[callable]:
        """Get a tool by name."""
        if not self.is_allowed(name):
            return None
        return self._tools.get(name)

    def list_tools(self) -> list:
        """List available tools."""
        if self.allowed_tools is None:
            return list(self._tools.keys())
        return [t for t in self._tools.keys() if t in self.allowed_tools]

    def get_tool_schemas(self) -> Dict[str, Dict]:
        """Get JSON schemas for all available tools."""
        schemas = {
            ToolType.BASH_EXEC.value: {
                "name": ToolType.BASH_EXEC.value,
                "description": "Execute bash commands and scripts",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Bash command to execute"},
                        "working_dir": {"type": "string", "description": "Working directory"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                        "env_vars": {"type": "object", "description": "Environment variables"}
                    },
                    "required": ["command"]
                }
            },
            ToolType.FILE_READ.value: {
                "name": ToolType.FILE_READ.value,
                "description": "Read file contents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"},
                        "limit": {"type": "integer", "description": "Max lines to read"}
                    },
                    "required": ["path"]
                }
            },
            ToolType.FILE_WRITE.value: {
                "name": ToolType.FILE_WRITE.value,
                "description": "Write content to files",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                        "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False}
                    },
                    "required": ["path", "content"]
                }
            },
            ToolType.COMPUTER_USE.value: {
                "name": ToolType.COMPUTER_USE.value,
                "description": "Simulate cursor/keyboard (placeholder - requires pyautogui)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["type", "click", "press", "screenshot"]},
                        "text": {"type": "string", "description": "Text for type action"},
                        "x": {"type": "integer", "description": "X coordinate"},
                        "y": {"type": "integer", "description": "Y coordinate"},
                        "key": {"type": "string", "description": "Key to press"}
                    },
                    "required": ["action"]
                }
            }
        }

        if self.allowed_tools:
            return {k: v for k, v in schemas.items() if k in self.allowed_tools}
        return schemas

    async def bash_exec(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: int = 30,
        env_vars: Optional[Dict[str, str]] = None
    ) -> ToolResult:
        """Execute a bash command.

        Args:
            command: Bash command to execute
            working_dir: Working directory (default: current)
            timeout: Timeout in seconds
            env_vars: Additional environment variables

        Returns:
            ToolResult with stdout/stderr
        """
        logger.debug("Executing bash command", command=command[:100])

        # Prepare environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        # Prepare working directory
        cwd = Path(working_dir).resolve() if working_dir else Path.cwd()

        try:
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            return ToolResult(
                success=process.returncode == 0,
                output=stdout.decode('utf-8', errors='replace'),
                error=stderr.decode('utf-8', errors='replace') if stderr else None,
                exit_code=process.returncode
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout} seconds",
                exit_code=-1
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                exit_code=-1
            )

    async def file_read(self, path: str, limit: Optional[int] = None) -> ToolResult:
        """Read a file.

        Args:
            path: File path
            limit: Maximum lines to read

        Returns:
            ToolResult with file content
        """
        try:
            file_path = Path(path).resolve()

            # Security check: prevent reading outside allowed directories
            # (simplified - production should have proper sandboxing)
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}"
                )

            content = file_path.read_text(encoding='utf-8')

            if limit:
                lines = content.split('\n')[:limit]
                content = '\n'.join(lines)

            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(file_path), "size": len(content)}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read file: {e}"
            )

    async def file_write(
        self,
        path: str,
        content: str,
        append: bool = False
    ) -> ToolResult:
        """Write to a file.

        Args:
            path: File path
            content: Content to write
            append: Append to file instead of overwrite

        Returns:
            ToolResult
        """
        try:
            file_path = Path(path)

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = 'a' if append else 'w'
            file_path.write_text(content, encoding='utf-8')

            return ToolResult(
                success=True,
                output=f"File {'appended' if append else 'written'}: {path}",
                metadata={"path": str(file_path), "bytes_written": len(content)}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {e}"
            )

    async def computer_use(
        self,
        action: str,
        text: Optional[str] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        key: Optional[str] = None
    ) -> ToolResult:
        """Simulate computer interactions.

        This is a placeholder implementation. Production would use pyautogui
        or similar library with proper sandboxing.

        Args:
            action: Action to perform (type, click, press, screenshot)
            text: Text to type
            x: X coordinate for click
            y: Y coordinate for click
            key: Key to press

        Returns:
            ToolResult
        """
        # Placeholder - would integrate with pyautogui in production
        logger.warning(
            "Computer use is a placeholder",
            action=action,
            has_text=bool(text),
            has_coords=bool(x is not None and y is not None)
        )

        return ToolResult(
            success=True,
            output=f"[Placeholder] Would perform {action} action",
            metadata={"action": action, "implemented": False}
        )
