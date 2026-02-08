"""
Tool Registry for Agent Service

This module manages all available tools for the agent service.
Tools include both native implementations and Langflow-exported flows.

To add a new tool:
    1. Create the tool implementation or Langflow export
    2. Import it here
    3. Add it to the ALL_TOOLS list
    4. Update the get_tool() and list_tools() functions if needed
"""

from typing import Dict, List, Type, Optional, Any
import logging

from .langflow_tool import (
    LangflowToolWrapper,
    FraudDetectionInput,
    FraudDetectionOutput,
)
from .langflow_flows.fraud_detection import FraudDetectionFlow

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Native Tool Implementations (if any)
# =============================================================================

# Placeholder for native tools that don't come from Langflow
# Example:
# class CalculatorTool(BaseTool):
#     name = "calculator"
#     description = "Perform mathematical calculations"
#     ...


# =============================================================================
# Langflow Flow Tool Wrappers
# =============================================================================

class FraudDetectionTool(LangflowToolWrapper):
    """
    Fraud detection tool powered by Langflow-exported flow.

    This tool analyzes insurance claims for potential fraud indicators including:
    - High claim amounts (above 10M VND threshold)
    - Suspicious velocity patterns (multiple claims in short period)
    - Risky keywords in notes ("urgent", "emergency", "bypass", etc.)
    - High-risk diagnosis codes

    Exported from Langflow flow: "Fraud Detection v1"
    """

    name = "fraud_detection"
    description = (
        "Analyze insurance claims for fraud indicators. "
        "Checks claim amount, velocity patterns, suspicious keywords, and diagnosis codes. "
        "Returns risk score (0-1), risk level, flags, and recommendations."
    )
    input_schema = FraudDetectionInput
    output_schema = FraudDetectionOutput
    flow_class = FraudDetectionFlow


# =============================================================================
# Tool Registry
# =============================================================================

# Master list of all available tools
ALL_TOOLS: List[Type[LangflowToolWrapper]] = [
    FraudDetectionTool,
    # Add new tools here
]

# Tool registry dictionary for quick lookup
_TOOL_REGISTRY: Dict[str, LangflowToolWrapper] = {}


def initialize_registry() -> None:
    """
    Initialize the tool registry.

    This should be called once at application startup.
    """
    global _TOOL_REGISTRY
    _TOOL_REGISTRY = {}

    for tool_class in ALL_TOOLS:
        try:
            tool_instance = tool_class()
            _TOOL_REGISTRY[tool_instance.name] = tool_instance
            logger.info(f"Registered tool: {tool_instance.name}")
        except Exception as e:
            logger.error(f"Failed to register tool {tool_class.__name__}: {e}")

    logger.info(f"Tool registry initialized with {len(_TOOL_REGISTRY)} tools")


def get_tool(name: str) -> Optional[LangflowToolWrapper]:
    """
    Get a tool by name.

    Args:
        name: The tool name

    Returns:
        Tool instance or None if not found
    """
    if not _TOOL_REGISTRY:
        initialize_registry()

    tool = _TOOL_REGISTRY.get(name)
    if tool is None:
        logger.warning(f"Tool not found: {name}")
    return tool


def list_tools() -> List[Dict[str, Any]]:
    """
    List all available tools with their schemas.

    Returns:
        List of tool schema dictionaries
    """
    if not _TOOL_REGISTRY:
        initialize_registry()

    return [tool.get_schema() for tool in _TOOL_REGISTRY.values()]


def execute_tool(name: str, **kwargs) -> Dict[str, Any]:
    """
    Execute a tool by name with the given parameters.

    Args:
        name: Tool name
        **kwargs: Tool parameters

    Returns:
        Tool execution result
    """
    tool = get_tool(name)
    if tool is None:
        return {
            "status": "error",
            "error": f"Tool '{name}' not found",
            "available_tools": list(_TOOL_REGISTRY.keys()),
        }

    try:
        import asyncio
        # Handle both sync and async execution
        if asyncio.iscoroutinefunction(tool.execute):
            return asyncio.run(tool.execute(**kwargs))
        else:
            return tool.execute(**kwargs)
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def execute_tool_async(name: str, **kwargs) -> Dict[str, Any]:
    """
    Async version of execute_tool.

    Args:
        name: Tool name
        **kwargs: Tool parameters

    Returns:
        Tool execution result
    """
    tool = get_tool(name)
    if tool is None:
        return {
            "status": "error",
            "error": f"Tool '{name}' not found",
            "available_tools": list(_TOOL_REGISTRY.keys()),
        }

    try:
        return await tool.execute(**kwargs)
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


def register_tool(tool_class: Type[LangflowToolWrapper]) -> None:
    """
    Dynamically register a new tool at runtime.

    Args:
        tool_class: The tool class to register
    """
    global _TOOL_REGISTRY

    if not _TOOL_REGISTRY:
        initialize_registry()

    try:
        tool_instance = tool_class()
        _TOOL_REGISTRY[tool_instance.name] = tool_instance
        ALL_TOOLS.append(tool_class)
        logger.info(f"Dynamically registered tool: {tool_instance.name}")
    except Exception as e:
        logger.error(f"Failed to register tool {tool_class.__name__}: {e}")


# Initialize on module load
initialize_registry()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Tool classes
    "FraudDetectionTool",
    # Registry functions
    "get_tool",
    "list_tools",
    "execute_tool",
    "execute_tool_async",
    "register_tool",
    "initialize_registry",
    # Constants
    "ALL_TOOLS",
]
