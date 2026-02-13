"""Tool registry for managing available tools."""
from typing import Dict, List

from tools.base import BaseTool
from tools.coverage_calc import CoverageCalcTool
from tools.document_query import DocumentQueryTool
from tools.icd_lookup import ICDLookupTool
from tools.langflow_tool import FraudDetectionTool
from tools.policy_check import PolicyCheckTool


class ToolRegistry:
    """Registry for managing and accessing tools."""

    def __init__(self):
        """Initialize empty registry."""
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None
        """
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_tool_schemas(self) -> List[dict]:
        """Get schemas for all tools.

        Returns:
            List of tool schemas
        """
        return [tool.get_schema() for tool in self._tools.values()]

    def register_defaults(self) -> None:
        """Register default tools."""
        self.register(ICDLookupTool())
        self.register(PolicyCheckTool())
        self.register(CoverageCalcTool())
        self.register(DocumentQueryTool())
        self.register(FraudDetectionTool())


# Global registry instance
_registry = ToolRegistry()
_registry.register_defaults()


def get_registry() -> ToolRegistry:
    """Get global tool registry."""
    return _registry
