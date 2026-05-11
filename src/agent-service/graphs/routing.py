"""Routing functions for the multi-agent workflow graph."""

from graphs.constants import HUMAN_REVIEW, STAGE_COMPLETENESS, STAGE_QUALITY
from graphs.state import GraphState
from graphs.workflow_policy import (
    decision_from_result,
    human_decision_from_state,
    next_after_agent_review,
    next_after_human_review,
    next_after_human_stage_review,
    next_after_ocr_extraction,
    next_after_stage_accept,
    next_after_stage_assessment,
    review_stage_from_state,
    stage_policy,
)

_get_decision_from_result = decision_from_result
_get_human_decision = human_decision_from_state
_review_stage_from_state = review_stage_from_state


def _route_after_completeness_success(state: GraphState) -> str:
    """Route successful completeness based on the available OCR stage."""
    return next_after_stage_accept(state, stage_policy(STAGE_COMPLETENESS))


def route_after_completeness(state: GraphState) -> str:
    """Route after completeness check based on agent_1_result."""
    return next_after_stage_assessment(state, STAGE_COMPLETENESS)


def route_after_quality(state: GraphState) -> str:
    """Route after quality check based on agent_2_result."""
    return next_after_stage_assessment(state, STAGE_QUALITY)


def route_after_agent_review(state: GraphState) -> str:
    """Route after the agent_review node based on auto-review status.

    The agent_review node is expected to update the corresponding agent
    result with ``is_auto_reviewed=True`` when it is confident that no
    further human intervention is required. This function inspects that
    flag to decide whether to proceed to the next automated stage or
    fall back to human review:

    * For completeness-related steps, it routes by OCR stage when
      ``is_auto_reviewed`` is true, otherwise to ``human_review``.
    * For quality-related steps, it routes to ``final_decision`` when
      ``is_auto_reviewed`` is true, otherwise to ``human_review``.

    Args:
        state: Current graph state.

    Returns:
        The name of the next node: either the appropriate next automated
        stage (``ocr_extraction``, ``quality_check``, or ``final_decision``)
        or ``human_review``.
    """
    return next_after_agent_review(state)


def route_after_final_review(state: GraphState) -> str:
    """Route from final decision node.

    The DecisionAgent has provided a comprehensive recommendation. We now
    force human intervention for the ultimate sign-off. The DecisionAgent
    schema only allows ``approve`` or ``reject``, so all paths lead to
    ``human_review``.
    """
    # WHY: FinalDecisionOutput.decision is Literal["approve", "reject"].
    # No "edit" branch exists for the final agent — all results require
    # human sign-off before the workflow can complete.
    return HUMAN_REVIEW


def route_after_completeness_review(state: GraphState) -> str:
    """Route from completeness review stage."""
    return next_after_human_stage_review(state, STAGE_COMPLETENESS)


def route_after_quality_review(state: GraphState) -> str:
    """Route from quality review stage."""
    return next_after_human_stage_review(state, STAGE_QUALITY)


def route_after_ocr_extraction(state: GraphState) -> str:
    """Route after OCR phase 2 extraction."""
    return next_after_ocr_extraction(state)


def route_after_human_review(state: GraphState) -> str:
    """Main router from human review node to the next appropriate node based on stage."""
    return next_after_human_review(state)
