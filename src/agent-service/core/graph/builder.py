"""Graph builder for ReAct agent."""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from core.graph.state import AgentState
from core.graph.nodes import (
    observe_node,
    think_node,
    act_node,
    reflect_node,
    decide_node
)
from core.graph.edges import should_continue


def build_claim_agent(checkpointer: BaseCheckpointSaver = None) -> StateGraph:
    """Build the ReAct agent graph for claim processing.

    The graph implements the ReAct (Reasoning + Acting) loop:
    1. Observe - Gather information from extraction and context
    2. Think - Generate reasoning about what to do
    3. Act - Execute appropriate tool
    4. Reflect - Evaluate results and decide whether to continue
    5. Decide - Make final decision (terminal node)

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled StateGraph ready for execution
    """
    # Initialize the graph with our state type
    workflow = StateGraph(AgentState)

    # === Add Nodes ===
    workflow.add_node("observe", observe_node)
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("decide", decide_node)

    # === Set Entry Point ===
    workflow.set_entry_point("observe")

    # === Add Edges ===
    # Observe -> Think -> Act -> Reflect (linear flow)
    workflow.add_edge("observe", "think")
    workflow.add_edge("think", "act")
    workflow.add_edge("act", "reflect")

    # Reflect has conditional edge:
    # - If should_continue: go back to Observe for next iteration
    # - If not: go to Decide for final decision
    workflow.add_conditional_edges(
        "reflect",
        should_continue,
        {
            "continue": "observe",  # Loop back for more info
            "decide": "decide"      # Proceed to final decision
        }
    )

    # Decide is terminal
    workflow.add_edge("decide", END)

    # === Compile ===
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()


def get_graph_visualization() -> str:
    """Get a text representation of the graph structure."""
    return """
    ┌─────────┐
    │  Start  │
    └────┬────┘
         ▼
    ┌─────────┐
    │ Observe │
    └────┬────┘
         ▼
    ┌─────────┐
    │  Think  │
    └────┬────┘
         ▼
    ┌─────────┐
    │   Act   │
    └────┬────┘
         ▼
    ┌─────────┐
    │ Reflect │
    └────┬────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│Observe │ │ Decide │
│(loop)  │ │ (end)  │
└────────┘ └────┬───┘
                ▼
           ┌─────────┐
           │   END   │
           └─────────┘
    """