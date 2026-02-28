"""Base tool abstract class for multi-agent system.

This module defines the abstract base class that all tools must inherit from
to ensure consistent interface and OpenAI function calling compatibility.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


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

    def _normalize_string(self, value: Any) -> str:
        """Normalize input value to a lowercase string.

        Handles strings, lists (joins them), and None.

        Args:
            value: Input value to normalize.

        Returns:
            Normalized lowercase string.
        """
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(str(v) for v in value).lower()
        return str(value).lower()

    def _calculate_severity_score(self, issues: List[Dict[str, Any]]) -> float:
        """Calculate overall severity score from 0.0 (clean) to 1.0 (critical).

        Aggregates issue severities using weighted scoring:
        - high severity: 1.0 weight
        - medium severity: 0.5 weight
        - low severity: 0.2 weight

        The score is normalized by dividing by a scaling factor of 5.0,
        ensuring that multiple lower-severity issues can accumulate to
        approach the maximum score, while capping at 1.0.

        Args:
            issues: List of issue dictionaries, each containing a 'severity' key
                   with values 'high', 'medium', or 'low'.

        Returns:
            Float between 0.0 (no issues) and 1.0 (maximum severity).
        """
        if not issues:
            return 0.0
        weights = {"high": 1.0, "medium": 0.5, "low": 0.2}
        total_weight = sum(weights.get(issue.get("severity", "medium"), 0.5) for issue in issues)
        return min(1.0, total_weight / 5.0)
