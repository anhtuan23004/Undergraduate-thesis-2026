"""Graph builder for ReAct agent."""
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from core.graph.edges import should_continue
from core.graph.nodes import act_node, decide_node, observe_node, reflect_node, think_node
from core.graph.state import AgentState


GRAPH_VISUALIZATION = """
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


def build_claim_agent(checkpointer: BaseCheckpointSaver | None = None) -> StateGraph:
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
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("observe", observe_node)
    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("decide", decide_node)

    # Set entry point
    workflow.set_entry_point("observe")

    # Add edges
    workflow.add_edge("observe", "think")
    workflow.add_edge("think", "act")
    workflow.add_edge("act", "reflect")

    workflow.add_conditional_edges(
        "reflect",
        should_continue,
        {
            "continue": "observe",
            "decide": "decide"
        }
    )

    workflow.add_edge("decide", END)

    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()


def get_graph_visualization() -> str:
    """Get a text representation of the graph structure."""
    return GRAPH_VISUALIZATION
