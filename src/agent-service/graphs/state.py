"""
GraphState definition for the multi-agent system.

This module defines the state structure used by the LangGraph workflow,
including all fields needed for agent communication and state management.
"""

import operator
from typing import Annotated, Literal, TypedDict

WorkflowStage = Literal["completeness", "quality", "final", "none"]
WorkflowStatus = Literal["running", "paused", "waiting_human", "completed", "error"]


class GraphState(TypedDict):
    """
    State definition for the multi-agent graph workflow.

    This TypedDict defines all fields that are passed between nodes
    in the LangGraph workflow, enabling stateful multi-agent processing
    with human-in-the-loop review capabilities.
    """

    run_id: str
    """Technical run identifier for v2 run-based API."""

    # Input fields
    claim_id: str
    """Unique identifier for the claim being processed."""

    policy_number: str
    """Policy number associated with the claim."""

    input_file: str
    """Path to the input file being processed."""

    extracted_documents: dict
    """Documents extracted from the input file (OCR results, etc.)."""

    # Agent results
    agent_1_result: dict | None
    """Result from Agent 1 (initial processing/extraction)."""

    agent_2_result: dict | None
    """Result from Agent 2 (secondary processing/validation)."""

    # Human review
    human_review_result: dict | None
    """Result from human review step (approval, corrections, etc.)."""

    edited_agent_1_result: dict | None
    """Human-edited result for Agent 1 (completeness)."""

    edited_agent_2_result: dict | None
    """Human-edited result for Agent 2 (quality)."""

    # Final output
    final_result: dict | None
    """Final processed result after all agents and review."""

    # Workflow state
    history: Annotated[list, operator.add]
    """Accumulated history of actions and decisions using operator.add reducer."""

    current_step: str
    """Current step in the workflow (for tracking progress)."""

    active_stage: WorkflowStage
    """Current automated workflow stage."""

    review_stage: WorkflowStage
    """Stage that currently needs agent or human review."""

    workflow_status: WorkflowStatus
    """Machine-readable workflow lifecycle status."""

    should_continue: bool
    """Flag indicating whether the workflow should continue or halt."""

    error: str | None
    """Error message if any step fails."""

    pending_human_review: bool
    """Flag indicating whether this workflow is currently waiting for human review."""
