"""Base tool abstract class for multi-agent system.

This module defines the abstract base class that all tools must inherit from
to ensure consistent interface and OpenAI function calling compatibility.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """Abstract base class for all tools in the multi-agent system.

    All tools must inherit from this class and implement the required
    abstract methods. The class provides automatic OpenAI function schema
    generation for tool calling.

    Attributes:
        name: The tool name used for function calling.
        description: A description of what the tool does.
        parameters: JSON Schema defining the tool's parameters.
    """

    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool with the given parameters.

        Args:
            **kwargs: The parameters defined in the tool's schema.

        Returns:
            A dictionary containing the tool's execution result.
            Should always include at least a 'success' boolean key.
        """
        pass

    def get_openai_schema(self) -> Dict[str, Any]:
        """Generate OpenAI function calling schema for this tool.

        Returns:
            A dictionary in OpenAI function calling format containing:
            - type: "function"
            - function: Object with name, description, and parameters schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
