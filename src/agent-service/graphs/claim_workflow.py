"""Main claim processing workflow (LangGraph)."""

from typing import Any

import structlog
from agents import CompletenessAgentFactory, DecisionAgentFactory, QualityAgentFactory
from config import settings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END as LANGGRAPH_END
from langgraph.graph import StateGraph

from graphs.constants import (
    AGENT_REVIEW,
    COMPLETENESS_CHECK,
    END,
    FINAL_DECISION,
    HUMAN_REVIEW,
    OCR_EXTRACTION,
    QUALITY_CHECK,
)
from graphs.routing import (
    route_after_agent_review,
    route_after_completeness,
    route_after_final_review,
    route_after_human_review,
    route_after_ocr_extraction,
    route_after_quality,
)
from graphs.state import GraphState

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

    workflow.add_node(COMPLETENESS_CHECK, c_factory.create_completeness_agent())
    from graphs.ocr_extraction import run_ocr_extraction

    workflow.add_node(OCR_EXTRACTION, run_ocr_extraction)
    workflow.add_node(QUALITY_CHECK, q_factory.create_quality_agent())
    workflow.add_node(FINAL_DECISION, d_factory.create_decision_agent())

    from graphs.agent_review import AgentReviewNode
    from graphs.human_review import HumanReviewNode

    h_node = HumanReviewNode()
    a_node = AgentReviewNode(llm_client)
    workflow.add_node(HUMAN_REVIEW, h_node.run)
    workflow.add_node(AGENT_REVIEW, a_node.run)

    workflow.set_entry_point(COMPLETENESS_CHECK)

    workflow.add_conditional_edges(
        COMPLETENESS_CHECK,
        route_after_completeness,
        {
            OCR_EXTRACTION: OCR_EXTRACTION,
            FINAL_DECISION: FINAL_DECISION,
            AGENT_REVIEW: AGENT_REVIEW,
        },
    )

    workflow.add_conditional_edges(
        OCR_EXTRACTION,
        route_after_ocr_extraction,
        {
            QUALITY_CHECK: QUALITY_CHECK,
            FINAL_DECISION: FINAL_DECISION,
        },
    )

    workflow.add_conditional_edges(
        QUALITY_CHECK,
        route_after_quality,
        {
            FINAL_DECISION: FINAL_DECISION,
            AGENT_REVIEW: AGENT_REVIEW,
        },
    )

    workflow.add_conditional_edges(
        AGENT_REVIEW,
        route_after_agent_review,
        {
            OCR_EXTRACTION: OCR_EXTRACTION,
            QUALITY_CHECK: QUALITY_CHECK,
            FINAL_DECISION: FINAL_DECISION,
            HUMAN_REVIEW: HUMAN_REVIEW,
        },
    )

    workflow.add_conditional_edges(
        FINAL_DECISION,
        route_after_final_review,
        {
            QUALITY_CHECK: QUALITY_CHECK,
            HUMAN_REVIEW: HUMAN_REVIEW,
        },
    )

    workflow.add_conditional_edges(
        HUMAN_REVIEW,
        route_after_human_review,
        {
            COMPLETENESS_CHECK: COMPLETENESS_CHECK,
            OCR_EXTRACTION: OCR_EXTRACTION,
            QUALITY_CHECK: QUALITY_CHECK,
            FINAL_DECISION: FINAL_DECISION,
            END: LANGGRAPH_END,
        },
    )

    memory = checkpointer or MemorySaver()

    interrupts = [HUMAN_REVIEW]
    if settings.PAUSE_AT_EACH_STAGE:
        interrupts.extend([QUALITY_CHECK, FINAL_DECISION])

    return workflow.compile(
        checkpointer=memory,
        interrupt_before=interrupts,
    )
