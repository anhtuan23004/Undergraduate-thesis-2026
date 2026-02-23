"""Graph builder for the multi-agent workflow.

This module constructs the LangGraph StateGraph that orchestrates
the multi-agent workflow including completeness check, quality check,
human review, and final decision nodes.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from core.state import GraphState
from agents.completeness_agent import CompletenessAgent
from agents.quality_agent import QualityAgent
from agents.human_review import HumanReviewNode
from agents.final_agent import FinalAgent
from core.router import (
    route_after_completeness,
    route_after_quality,
    route_after_human_review
)


GRAPH_VISUALIZATION = """
    ┌─────────────────┐
    │  Start          │
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ Completeness    │     ┌─────────────┐
    │ Check (Agent 1) │────▶│ Reject      │
    └────────┬────────┘     └─────────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        ▼
┌───────┐ ┌───────┐ ┌─────────────┐
│Accept │ │Edit   │ │   Reject    │
│       │ │Needed │ │             │
└───┬───┘ └───┬───┘ └──────┬──────┘
    │         │            │
    ▼         ▼            ▼
┌───────┐ ┌─────────────┐ ┌─────────────┐
│Quality│ │ Human       │ │  Final      │
│Check  │ │ Review      │ │  Decision   │
│(Agent2)│ │             │ │             │
└───┬───┘ └──────┬──────┘ └─────────────┘
    │            │
    │    ┌───────┴───────┐
    │    │               │
    ▼    ▼               ▼
┌───────┐ ┌───────┐ ┌─────────────┐
│Pass/  │ │Edit   │ │   Reject    │
│Fail   │ │Made   │ │             │
└───┬───┘ └───┬───┘ └──────┬──────┘
    │         │            │
    ▼         ▼            ▼
┌─────────────┐ ┌─────────────────┐
│  Final      │ │ Quality Check   │
│  Decision   │ │ (loop back)     │
│             │ └─────────────────┘
└──────┬──────┘
       ▼
  ┌─────────┐
  │   END   │
  └─────────┘
"""


def build_multi_agent_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Build the multi-agent workflow graph.

    Constructs a StateGraph with the following workflow:
    1. Completeness Check (Agent 1) - Validates document completeness
    2. Quality Check (Agent 2) - Validates quality and consistency
    3. Human Review - Human-in-the-loop for edge cases
    4. Final Decision - Aggregates results and produces final output

    Routing logic:
    - Completeness accept → Quality Check
    - Completeness reject → Final Decision
    - Completeness accept_with_edit → Human Review
    - Quality accept/reject → Final Decision
    - Quality accept_with_edit → Human Review
    - Human approve/reject → Final Decision
    - Human edit → Quality Check (loop back)

    Args:
        checkpointer: Optional checkpointer for state persistence across
            workflow executions.

    Returns:
        Compiled StateGraph ready for execution.
    """
    workflow = StateGraph(GraphState)

    # Initialize agents
    completeness = CompletenessAgent()
    quality = QualityAgent()
    human = HumanReviewNode()
    final = FinalAgent()

    # Add nodes
    workflow.add_node("completeness_check", completeness.run)
    workflow.add_node("quality_check", quality.run)
    workflow.add_node("human_review", human.run)
    workflow.add_node("final_decision", final.run)

    # Set entry point
    workflow.set_entry_point("completeness_check")

    # Add conditional edges from completeness_check
    workflow.add_conditional_edges(
        "completeness_check",
        route_after_completeness,
        {
            "quality_check": "quality_check",
            "final_decision": "final_decision",
            "human_review": "human_review"
        }
    )

    # Add conditional edges from quality_check
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {
            "final_decision": "final_decision",
            "human_review": "human_review"
        }
    )

    # Add conditional edges from human_review
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "final_decision": "final_decision",
            "quality_check": "quality_check"
        }
    )

    # Final decision goes to END
    workflow.add_edge("final_decision", END)

    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()


def get_graph_visualization() -> str:
    """Get a text representation of the graph structure."""
    return GRAPH_VISUALIZATION
