"""Multi-agent insurance claims processing system.

This package implements a sophisticated multi-agent workflow for processing
insurance claims using LangGraph with a 3-layer architecture.
"""

__version__ = "1.0.0"
__author__ = "Insurance Claims AI Team"

from multi_agent.core.state import GraphState
from multi_agent.core.graph import build_multi_agent_graph

__all__ = [
    "GraphState",
    "build_multi_agent_graph",
]