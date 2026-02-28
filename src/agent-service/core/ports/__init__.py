"""Domain ports (interfaces) for dependency injection.

This module defines abstract interfaces that the domain layer depends on.
Concrete implementations are provided in the infrastructure layer.
"""

from .llm_client import LLMClientInterface
from .config_loader import ConfigLoaderInterface

__all__ = ["LLMClientInterface", "ConfigLoaderInterface"]
