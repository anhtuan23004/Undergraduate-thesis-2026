"""Configuration management for multi-agent system.

Handles loading of YAML metadata, Markdown instructions, and JSON tool schemas.
"""

from multi_agent.config.loader import ConfigLoader

__all__ = [
    "ConfigLoader",
]