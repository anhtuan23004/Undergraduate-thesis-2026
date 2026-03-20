"""Main claim processing workflow (LangGraph)."""

import structlog
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graphs.state import GraphState
from graphs.routing import (
    route_after_completeness,
    route_after_quality,
    route_after_final_review,
)
from agents import CompletenessAgentFactory, QualityAgentFactory, DecisionAgentFactory

logger = structlog.get_logger()


def build_claim_workflow(
    llm_client: Any,
    checkpointer: Any = None,
) -> StateGraph:
    """Build the claim processing graph.

    Args:
        llm_client: Client for LLM interactions.
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).

    Returns:
        Compiled LangGraph workflow.
    """
    c_factory = CompletenessAgentFactory(llm_client)
    q_factory = QualityAgentFactory(llm_client)
    d_factory = DecisionAgentFactory(llm_client)

    workflow = StateGraph(GraphState)

    workflow.add_node("completeness_check", c_factory.create_completeness_agent())
    workflow.add_node("quality_check", q_factory.create_quality_agent())
    workflow.add_node("final_decision", d_factory.create_decision_agent())

    from graphs.human_review import HumanReviewNode

    h_node = HumanReviewNode()
    workflow.add_node("human_review", h_node.run)

    workflow.set_entry_point("completeness_check")

    workflow.add_conditional_edges(
        "completeness_check",
        route_after_completeness,
        {
            "quality_check": "quality_check",
            "final_decision": "final_decision",
            "human_review": "human_review",
        },
    )

    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {
            "final_decision": "final_decision",
            "human_review": "human_review",
        },
    )

    workflow.add_conditional_edges(
        "final_decision",
        route_after_final_review,
        {
            "end": END,
        },
    )

    memory = checkpointer or MemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["human_review"])
