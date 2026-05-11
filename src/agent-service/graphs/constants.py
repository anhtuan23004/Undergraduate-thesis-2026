"""Shared graph node, stage, and workflow status constants."""

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

# Severity levels (ordered highest → lowest)
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SEVERITY_ORDER = (SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)

# WHY: Routing uses this set to decide reject vs accept_with_edit.
SEVERITY_ESCALATION = frozenset({SEVERITY_CRITICAL, SEVERITY_HIGH})

# WHY: Agent review uses this set to decide hard constraint failure.
SEVERITY_REVIEW_REQUIRED = frozenset({SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM})
