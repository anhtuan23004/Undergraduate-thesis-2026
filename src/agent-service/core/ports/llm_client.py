"""LLM Client interface for the domain layer.

This module defines the abstract interface that the domain layer uses
for LLM interactions. Concrete implementations are provided in the
infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMClientInterface(ABC):
    """Abstract interface for LLM client operations.

    Implementations of this interface handle the actual communication
    with LLM providers (Gemini, OpenAI, etc.).
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate a text response from the LLM."""
        pass

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a JSON response from the LLM."""
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Any],
        tool_schemas: List[Dict[str, Any]],
        system_prompt: str,
        output_schema: Dict[str, Any],
        max_iterations: int = 6,
    ) -> Dict[str, Any]:
        """Run an agentic tool-calling loop."""
        pass
