"""Base class for tools."""
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """Base class for all agent tools."""

    name: str
    description: str

    @abstractmethod
    async def arun(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool asynchronously.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            Tool result as dictionary
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get tool input schema for LLM."""
        return {
            "name": self.name,
            "description": self.description
        }
