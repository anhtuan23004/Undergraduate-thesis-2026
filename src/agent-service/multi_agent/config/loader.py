"""Configuration loader for multi-agent system.

Handles loading and caching of YAML agent configs, Markdown instructions,
and JSON tool schemas.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Loads and caches configuration files for the multi-agent system.

    Supports loading:
    - YAML agent configurations from config/agents/
    - Markdown instructions from config/instructions/
    - JSON tool schemas from config/schemas/

    All loaded configurations are cached for performance.
    """

    def __init__(self, config_dir: str | None = None) -> None:
        """Initialize the config loader.

        Args:
            config_dir: Base configuration directory. If None, uses the
                directory containing this file.
        """
        if config_dir is None:
            self.config_dir = Path(__file__).parent
        else:
            self.config_dir = Path(config_dir)

        self.agents_dir = self.config_dir / "agents"
        self.instructions_dir = self.config_dir / "instructions"
        self.schemas_dir = self.config_dir / "schemas"

    def _ensure_dir_exists(self, directory: Path) -> None:
        """Ensure a configuration directory exists.

        Args:
            directory: Path to the directory to check.

        Raises:
            FileNotFoundError: If the directory does not exist.
        """
        if not directory.exists():
            raise FileNotFoundError(
                f"Configuration directory not found: {directory}"
            )

    @lru_cache(maxsize=128)
    def load_agent(self, agent_name: str) -> dict[str, Any]:
        """Load an agent configuration from a YAML file.

        Args:
            agent_name: Name of the agent (without .yaml extension).

        Returns:
            Dictionary containing the agent configuration.

        Raises:
            FileNotFoundError: If the agent configuration file does not exist.
            yaml.YAMLError: If the YAML file is malformed.
        """
        self._ensure_dir_exists(self.agents_dir)

        config_path = self.agents_dir / f"{agent_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Agent configuration not found: {config_path}"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @lru_cache(maxsize=128)
    def load_instructions(self, agent_name: str) -> str:
        """Load agent instructions from a Markdown file.

        Args:
            agent_name: Name of the agent (without .md extension).

        Returns:
            String containing the markdown instructions.

        Raises:
            FileNotFoundError: If the instructions file does not exist.
        """
        self._ensure_dir_exists(self.instructions_dir)

        instructions_path = self.instructions_dir / f"{agent_name}.md"

        if not instructions_path.exists():
            raise FileNotFoundError(
                f"Instructions file not found: {instructions_path}"
            )

        with open(instructions_path, "r", encoding="utf-8") as f:
            return f.read()

    @lru_cache(maxsize=128)
    def load_schema(self, tool_name: str) -> dict[str, Any]:
        """Load a tool schema from a JSON file.

        Args:
            tool_name: Name of the tool (without .json extension).

        Returns:
            Dictionary containing the JSON schema.

        Raises:
            FileNotFoundError: If the schema file does not exist.
            json.JSONDecodeError: If the JSON file is malformed.
        """
        self._ensure_dir_exists(self.schemas_dir)

        schema_path = self.schemas_dir / f"{tool_name}.json"

        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}"
            )

        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def clear_cache(self) -> None:
        """Clear all cached configurations."""
        self.load_agent.cache_clear()
        self.load_instructions.cache_clear()
        self.load_schema.cache_clear()

    def list_agents(self) -> list[str]:
        """List all available agent configurations.

        Returns:
            List of agent names (without .yaml extension).
        """
        if not self.agents_dir.exists():
            return []

        return [
            f.stem for f in self.agents_dir.glob("*.yaml")
        ]

    def list_instructions(self) -> list[str]:
        """List all available instruction files.

        Returns:
            List of instruction names (without .md extension).
        """
        if not self.instructions_dir.exists():
            return []

        return [
            f.stem for f in self.instructions_dir.glob("*.md")
        ]

    def list_schemas(self) -> list[str]:
        """List all available tool schemas.

        Returns:
            List of schema names (without .json extension).
        """
        if not self.schemas_dir.exists():
            return []

        return [
            f.stem for f in self.schemas_dir.glob("*.json")
        ]
