"""Configuration loader for multi-agent system.

Handles loading and caching of YAML agent configs, Markdown instructions,
and JSON tool schemas.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigLoader:
    """Loads and caches configuration files for the multi-agent system.

    Supports loading:
    - YAML agent configurations from features/*/config/
    - Markdown instructions from features/*/config/
    - JSON tool schemas from features/*/config/

    All loaded configurations are cached for performance.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        """Initialize the config loader.

        Args:
            base_dir: Base directory for agent-service. If None, uses the
                directory containing the 'core' folder.
        """
        if base_dir is None:
            # This file is in core/config/loader.py, so parent.parent.parent is agent-service/
            self.base_dir = Path(__file__).parent.parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.features_dir = self.base_dir / "features"

    def _find_file(self, name: str, extension: str) -> Path:
        """Find a configuration file by name and extension in features directory.

        Args:
            name: Base name of the file.
            extension: File extension (e.g., '.yaml', '.json', '.md').

        Returns:
            Path to the found file.

        Raises:
            FileNotFoundError: If the file is not found.
        """
        import logging

        logger = logging.getLogger(__name__)
        filename = f"{name}{extension}"

        # Search in features/*/config/
        matches = []
        for feature_config_dir in self.features_dir.glob("*/config"):
            path = feature_config_dir / filename
            if path.exists():
                matches.append(path)

        if len(matches) > 1:
            logger.warning(
                f"Multiple config files found for '{name}{extension}': "
                f"{matches}. Using first match: {matches[0]}"
            )

        if matches:
            return matches[0]

        raise FileNotFoundError(
            f"Configuration file not found: {filename} in {self.features_dir}"
        )

    @lru_cache(maxsize=128)
    def load_agent(self, agent_name: str) -> dict:
        """Load an agent configuration from a YAML file.

        Args:
            agent_name: Name of the agent (without .yaml extension).

        Returns:
            Dictionary containing the agent configuration.

        Raises:
            FileNotFoundError: If the agent configuration file does not exist.
            yaml.YAMLError: If the YAML file is malformed.
        """
        config_path = self._find_file(agent_name, ".yaml")

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
        instructions_path = self._find_file(agent_name, ".md")

        with open(instructions_path, "r", encoding="utf-8") as f:
            return f.read()

    @lru_cache(maxsize=128)
    def load_schema(self, tool_name: str) -> dict:
        """Load a tool schema from a JSON file.

        Args:
            tool_name: Name of the tool (without .json extension).

        Returns:
            Dictionary containing the JSON schema.

        Raises:
            FileNotFoundError: If the schema file does not exist.
            json.JSONDecodeError: If the JSON file is malformed.
        """
        schema_path = self._find_file(tool_name, ".json")

        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def clear_cache(self) -> None:
        """Clear all cached configurations."""
        self.load_agent.cache_clear()
        self.load_instructions.cache_clear()
        self.load_schema.cache_clear()

    def list_agents(self) -> list:
        """List all available agent configurations.

        Returns:
            List of agent names (without .yaml extension).
        """
        if not self.features_dir.exists():
            return []

        return [
            f.stem for f in self.features_dir.glob("*/config/*.yaml")
        ]

    def list_instructions(self) -> list:
        """List all available instruction files.

        Returns:
            List of instruction names (without .md extension).
        """
        if not self.features_dir.exists():
            return []

        return [
            f.stem for f in self.features_dir.glob("*/config/*.md")
        ]

    def list_schemas(self) -> list:
        """List all available tool schemas.

        Returns:
            List of schema names (without .json extension).
        """
        if not self.features_dir.exists():
            return []

        return [
            f.stem for f in self.features_dir.glob("*/config/*.json")
        ]
