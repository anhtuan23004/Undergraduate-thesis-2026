"""Graph builder for the multi-agent workflow.

This module constructs the LangGraph StateGraph that orchestrates
the multi-agent workflow including completeness check, quality check,
human review, and final decision nodes.

Workflow with Human Review at each step:
1. Completeness Check (Agent 1) → Human Review → Quality Check
2. Quality Check (Agent 2) → Human Review → Final Decision
3. Human Review → Final Decision
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from workflow.state import GraphState
from core.config.loader import ConfigLoader
from core.llm.client import LLMClient
from features.completeness.agent import CompletenessAgent
from features.quality.agent import QualityAgent
from features.orchestration.human_review import HumanReviewNode
from features.decision.agent import FinalAgent
from workflow.router import (
    route_after_completeness,
    route_after_quality,
    route_after_human_review
)


def build_multi_agent_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Build the multi-agent workflow graph with Human Review at each step.

    Constructs a StateGraph with the following workflow:
    1. Completeness Check (Agent 1) - Validates document completeness
    2. Human Review - Required approval after completeness check
    3. Quality Check (Agent 2) - Validates quality and consistency
    4. Human Review - Required approval after quality check
    5. Final Decision - Aggregates results and produces final output
    6. Human Review - Required approval before final decision

    Routing logic:
    - Completeness → Human Review → Quality Check (after approval)
    - Completeness reject → Human Review → Final Decision (after approval)
    - Quality → Human Review → Final Decision (after approval)
    - Human Review approve → proceed to next step
    - Human Review reject → proceed to Final Decision
    - Human Review edit → loop back to previous step

    Args:
        checkpointer: Optional checkpointer for state persistence across
            workflow executions.

    Returns:
        Compiled StateGraph ready for execution.
    """
    workflow = StateGraph(GraphState)

    # Initialize infrastructure dependencies (injected into domain agents)
    config_loader = ConfigLoader()
    llm_client = LLMClient()

    # Initialize agents with dependency injection
    completeness = CompletenessAgent(
        config_loader=config_loader,
        llm_client=llm_client
    )
    quality = QualityAgent(
        config_loader=config_loader,
        llm_client=llm_client
    )
    human = HumanReviewNode()
    final = FinalAgent(
        config_loader=config_loader,
        llm_client=llm_client
    )

    # Add nodes
    workflow.add_node("completeness_check", completeness.run)
    workflow.add_node("completeness_review", human.run)  # Human review after completeness
    workflow.add_node("quality_check", quality.run)
    workflow.add_node("quality_review", human.run)  # Human review after quality
    workflow.add_node("final_review", human.run)  # Human review before final decision
    workflow.add_node("final_decision", final.run)

    # Set entry point
    workflow.set_entry_point("completeness_check")

    # Step 1: Completeness Check → Human Review
    workflow.add_edge("completeness_check", "completeness_review")
    
    # After completeness human review: proceed based on approval
    workflow.add_conditional_edges(
        "completeness_review",
        route_after_human_review,
        {
            "quality_check": "quality_check",  # Approved - go to next step
            "final_decision": "final_decision"  # Rejected - end process
        }
    )

    # Step 2: Quality Check → Human Review
    workflow.add_edge("quality_check", "quality_review")
    
    # After quality human review: proceed based on approval
    workflow.add_conditional_edges(
        "quality_review",
        route_after_human_review,
        {
            "final_decision": "final_decision",  # Approved - proceed to final
            "completeness_check": "completeness_check"  # Edit - loop back
        }
    )

    # Step 3: Final Decision → Human Review → END
    workflow.add_edge("final_decision", "final_review")
    
    # After final human review: end the process
    workflow.add_conditional_edges(
        "final_review",
        route_after_human_review,
        {
            "final_decision": "final_decision",  # Approved - complete
            "quality_check": "quality_check"  # Edit - go back to quality
        }
    )

    # Final edge to END
    workflow.add_edge("final_decision", END)

    if checkpointer:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["completeness_review", "quality_review", "final_review"]
        )

    # Without checkpointer, we cannot resume from interrupts
    # so we don't set interrupt_before (graph will run straight through)
    return workflow.compile()
