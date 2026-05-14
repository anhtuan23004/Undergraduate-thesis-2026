"""Shared workflow contracts used across agents, graphs, and services."""

import operator
from typing import Annotated, Literal, TypedDict

COMPLETENESS_CHECK = "completeness_check"
OCR_EXTRACTION = "ocr_extraction"
QUALITY_CHECK = "quality_check"
AGENT_REVIEW = "agent_review"
HUMAN_REVIEW = "human_review"
FINAL_DECISION = "final_decision"
END = "end"

STAGE_COMPLETENESS = "completeness"
STAGE_QUALITY = "quality"
STAGE_FINAL = "final"
STAGE_NONE = "none"

STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_WAITING_HUMAN = "waiting_human"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

OCR_STAGE_NONE = "none"
OCR_STAGE_V1_DOCUMENT = "v1_document"
OCR_STAGE_PHASE1_CLASSIFIED = "phase1_classified"
OCR_STAGE_PHASE2_EXTRACTED = "phase2_extracted"
OCR_STAGE_ERROR = "error"

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SEVERITY_ORDER = (SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)
SEVERITY_ESCALATION = frozenset({SEVERITY_CRITICAL, SEVERITY_HIGH})
SEVERITY_REVIEW_REQUIRED = frozenset({SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM})

WorkflowStage = Literal["completeness", "quality", "final", "none"]
WorkflowStatus = Literal["running", "paused", "waiting_human", "completed", "error"]
OcrStage = Literal["none", "v1_document", "phase1_classified", "phase2_extracted", "error"]


class GraphState(TypedDict):
    """State definition for the multi-agent graph workflow."""

    run_id: str
    claim_id: str
    policy_number: str
    input_file: str
    file_hash: str | None
    extracted_documents: dict
    agent_1_result: dict | None
    agent_2_result: dict | None
    human_review_result: dict | None
    edited_agent_1_result: dict | None
    edited_agent_2_result: dict | None
    final_result: dict | None
    history: Annotated[list, operator.add]
    current_step: str
    active_stage: WorkflowStage
    review_stage: WorkflowStage
    workflow_status: WorkflowStatus
    ocr_stage: OcrStage
    should_continue: bool
    error: str | None
    pending_human_review: bool
