"""Config Loader interface for the domain layer.

This module defines the abstract interface that the domain layer uses
for loading configurations. Concrete implementations are provided in the
infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ConfigLoaderInterface(ABC):
    """Abstract interface for configuration loading operations.

    Implementations of this interface handle loading agent configurations,
    tool schemas, and instructions from various sources (files, databases,
    environment variables, etc.).
    """

    @abstractmethod
    def load_agent(self, agent_name: str) -> Dict[str, Any]:
        """Load an agent configuration.

        Args:
            agent_name: Name of the agent (e.g., "completeness_check_agent").

        Returns:
            Dictionary containing the agent configuration.

        Raises:
            FileNotFoundError: If agent configuration not found.
        """
        pass

    @abstractmethod
    def load_schema(self, tool_name: str) -> Dict[str, Any]:
        """Load a tool schema.

        Args:
            tool_name: Name of the tool.

        Returns:
            Dictionary containing the JSON schema.

        Raises:
            FileNotFoundError: If schema file not found.
        """
        pass

    @abstractmethod
    def load_instructions(self, instructions_name: str) -> str:
        """Load agent instructions.

        Args:
            instructions_name: Name of the instructions file (e.g., "completeness_agent").

        Returns:
            String containing the markdown instructions.

        Raises:
            FileNotFoundError: If instructions file not found.
        """
        pass

    @abstractmethod
    def list_agents(self) -> List[str]:
        """List all available agent configurations.

        Returns:
            List of agent names.
        """
        pass

    @abstractmethod
    def list_schemas(self) -> List[str]:
        """List all available tool schemas.

        Returns:
            List of schema names.
        """
        pass

    @abstractmethod
    def list_instructions(self) -> List[str]:
        """List all available instruction files.

        Returns:
            List of instruction names.
        """
        pass

    @abstractmethod
    def clear_cache(self) -> None:
        """Clear any cached configurations."""
        pass
