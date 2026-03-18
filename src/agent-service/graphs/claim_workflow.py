"""Main claim processing workflow (LangGraph).

Constructs the multi-agent orchestration graph using the refactored
agent factories and modular routing logic.
"""

import structlog
from typing import Any, Dict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graphs.state import GraphState
from graphs.routing import (
    route_after_completeness_review,
    route_after_quality_review,
    route_after_final_review,
)
from agents.completeness import CompletenessAgentFactory
from agents.quality import QualityAgentFactory
from agents.decision import DecisionAgentFactory

logger = structlog.get_logger()


def build_claim_workflow(
    config_loader: Any,
    llm_client: Any,
    checkpointer: Any = None,
) -> StateGraph:
    """Build the consolidated claim processing graph.

    Args:
        config_loader: Loader for agent/tool/schema configs.
        llm_client: Client for LLM interactions.
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).

    Returns:
        Compiled LangGraph workflow.
    """
    # Initialize factories
    c_factory = CompletenessAgentFactory(config_loader, llm_client)
    q_factory = QualityAgentFactory(config_loader, llm_client)
    d_factory = DecisionAgentFactory(config_loader, llm_client)

    # Create states graph
    workflow = StateGraph(GraphState)

    # Define Nodes
    workflow.add_node("completeness_check", c_factory.create_completeness_agent())
    workflow.add_node("quality_check", q_factory.create_quality_agent())
    workflow.add_node("final_decision", d_factory.create_decision_agent())

    # Placeholder node for Human Review interrupts
    # Actual logic is handled in the API layer/router
    from graphs.human_review import HumanReviewNode
    h_node = HumanReviewNode()
    workflow.add_node("human_review", h_node.run)

    # Define Edges
    workflow.set_entry_point("completeness_check")

    # Main path: Completeness -> Quality -> Final
    workflow.add_edge("completeness_check", "human_review")

    # Routing from Human Review (after completeness)
    workflow.add_conditional_edges(
        "human_review",
        route_after_completeness_review,
        {
            "quality_check": "quality_check",
            "completeness_check": "completeness_check",
            "final_decision": "final_decision",
        }
    )

    # Routing from Quality check
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality_review,
        {
            "final_decision": "final_decision",
            "quality_check": "quality_check",
        }
    )

    # Final routing
    workflow.add_conditional_edges(
        "final_decision",
        route_after_final_review,
        {
            "end": END,
            "completeness_check": "completeness_check",
        }
    )

    # Compile with checkpointer
    memory = checkpointer or MemorySaver()
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_review"]
    )
