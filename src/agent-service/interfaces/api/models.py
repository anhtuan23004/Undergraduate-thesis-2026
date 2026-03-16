"""Pydantic models for v2 run-based API."""

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


class RunCreateRequest(BaseModel):
    """Request for creating a new claim-processing run."""

    claim_id: str = Field(..., description="Business claim identifier")
    policy_number: str = Field(..., description="Policy number for the claim")
    input_file: str = Field(
        ...,
        description="Filename of the uploaded claim file (relative, inside uploads directory)",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional business metadata attached to the run",
    )

    @field_validator("input_file")
    @classmethod
    def validate_input_file(cls, value: str) -> str:
        """Reject absolute paths and path traversal; resolve to safe uploads dir."""
        import os
        from pathlib import Path

        if os.path.isabs(value):
            raise ValueError("input_file must be a relative filename, not an absolute path")
        if ".." in Path(value).parts:
            raise ValueError("input_file must not contain path traversal segments (..)")

        uploads_dir = Path(os.getenv("UPLOADS_DIR", "/tmp/agent-service/uploads")).resolve()

        if not uploads_dir.exists():
            try:
                uploads_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ValueError(f"Cannot create uploads directory: {exc}")

        resolved = (uploads_dir / value).resolve()

        try:
            resolved.relative_to(uploads_dir)
        except ValueError:
            raise ValueError("input_file must resolve to a path within the uploads directory")

        if not resolved.exists():
            raise ValueError(f"input_file does not exist: {value}")

        return str(resolved)


class RunCreateResponse(BaseModel):
    """Response after creating a run."""

    run_id: str = Field(..., description="Technical run identifier")
    claim_id: str = Field(..., description="Business claim identifier")
    status: Literal["created", "running"] = Field(..., description="Initial run status")
    created_at: str = Field(..., description="Run creation timestamp in ISO format")


class InterruptItem(BaseModel):
    """Granular HITL interrupt information."""

    interrupt_id: str = Field(..., description="Unique interrupt identifier")
    run_id: str = Field(..., description="Run identifier")
    stage: str = Field(..., description="Workflow stage where interrupt occurred")
    action: str = Field(..., description="Action requiring human decision")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Context payload for review")
    allowed_decisions: List[Literal["approve", "reject", "edit"]] = Field(
        default_factory=lambda: ["approve", "reject", "edit"],
        description="Allowed decisions for this interrupt",
    )
    created_at: str = Field(..., description="Interrupt creation timestamp in ISO format")


class RunStatusResponse(BaseModel):
    """Current status of a run."""

    run_id: str = Field(..., description="Run identifier")
    claim_id: Optional[str] = Field(default=None, description="Business claim identifier")
    status: Literal["created", "running", "interrupted", "completed", "failed"] = Field(
        ..., description="Current lifecycle status of the run"
    )
    current_stage: Optional[str] = Field(default=None, description="Current workflow stage")
    interrupts: List[InterruptItem] = Field(default_factory=list, description="Pending HITL interrupts")
    agent_1_result: Optional[Dict[str, Any]] = Field(default=None, description="Completeness result")
    agent_2_result: Optional[Dict[str, Any]] = Field(default=None, description="Quality result")
    final_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Canonical final output payload for v2 clients",
    )
    final_result: Optional[Dict[str, Any]] = Field(default=None, description="Final decision payload")
    error: Optional[str] = Field(default=None, description="Failure message when status=failed")
    updated_at: str = Field(..., description="Last update timestamp in ISO format")


class ResumeDecision(BaseModel):
    """A single human decision for an interrupt."""

    interrupt_id: str = Field(..., description="Interrupt identifier")
    decision: Literal["approve", "reject", "edit"] = Field(..., description="Human decision")
    comment: Optional[str] = Field(default="", description="Optional reviewer note")
    edited_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional edited payload for decision='edit'",
    )


class ResumeRunRequest(BaseModel):
    """Request to resume a run with HITL decisions."""

    decisions: List[ResumeDecision] = Field(..., min_length=1, description="List of decisions")
    reviewed_by: str = Field(default="human_reviewer", description="Reviewer identifier")


class ResumeRunResponse(BaseModel):
    """Response after resuming a run."""

    run_id: str = Field(..., description="Run identifier")
    status: Literal["running", "interrupted", "completed", "failed"] = Field(
        ..., description="Current status after applying decisions"
    )
    message: str = Field(..., description="Human-readable status message")
