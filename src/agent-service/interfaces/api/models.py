"""Pydantic models for multi-agent API."""
from typing import List, Dict, Any, Optional, Literal

from pydantic import BaseModel, Field, field_validator


class Issue(BaseModel):
    """Issue found during claim processing."""

    severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Issue severity level"
    )
    description: str = Field(
        ...,
        description="Description of the issue"
    )
    field: Optional[str] = Field(
        None,
        description="Field affected by the issue"
    )


class AgentResult(BaseModel):
    """Result from an agent's processing."""

    decision: Literal["accept", "reject", "accept_with_edit"] = Field(
        ...,
        description="Agent decision"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    reasoning: str = Field(
        ...,
        description="Reasoning for the decision"
    )
    missing_documents: Optional[List[str]] = Field(
        None,
        description="Missing documents if any"
    )
    issues: Optional[List[Issue]] = Field(
        None,
        description="Issues found"
    )


class MultiAgentRequest(BaseModel):
    """Request for multi-agent claim processing."""

    claim_id: str = Field(
        ...,
        description="Unique claim identifier"
    )
    input_file: str = Field(
        ...,
        description="Filename of the uploaded claim file (relative, inside uploads directory)"
    )
    policy_number: str = Field(
        ...,
        description="Policy number for the claim"
    )

    @field_validator("input_file")
    @classmethod
    def validate_input_file(cls, v: str) -> str:
        """Reject absolute paths and path traversal; resolve to safe uploads dir."""
        import os
        from pathlib import Path

        # Reject any absolute path or traversal sequences before resolution
        if os.path.isabs(v):
            raise ValueError("input_file must be a relative filename, not an absolute path")
        if ".." in Path(v).parts:
            raise ValueError("input_file must not contain path traversal segments (..)")

        # Resolve against the configured uploads directory
        uploads_dir = Path(os.getenv("UPLOADS_DIR", "/tmp/agent-service/uploads")).resolve()

        # Ensure the uploads directory exists
        if not uploads_dir.exists():
            try:
                uploads_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ValueError(f"Cannot create uploads directory: {e}")

        resolved = (uploads_dir / v).resolve()

        # Ensure the resolved path is still inside uploads_dir
        try:
            resolved.relative_to(uploads_dir)
        except ValueError:
            raise ValueError("input_file must resolve to a path within the uploads directory")

        # Check if file exists
        if not resolved.exists():
            raise ValueError(f"input_file does not exist: {v}")

        return str(resolved)


class MultiAgentResponse(BaseModel):
    """Response from multi-agent claim processing."""

    claim_id: str = Field(
        ...,
        description="Claim identifier"
    )
    final_decision: str = Field(
        ...,
        description="Final decision: APPROVE/REJECT/PENDING"
    )
    agent_1_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Completeness check result"
    )
    agent_2_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Quality check result"
    )
    human_review_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Human review result"
    )
    processing_steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Workflow history"
    )


class ClaimStatusResponse(BaseModel):
    """Response for claim status check."""

    claim_id: str = Field(
        ...,
        description="Claim identifier"
    )
    status: Literal["starting", "running", "interrupted", "finished", "error"] = Field(
        ...,
        description="Current status of the claim processing"
    )
    agent_1_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Completeness check result"
    )
    agent_2_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Quality check result"
    )
    human_review_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Human review result"
    )
    final_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Final decision result"
    )
    pending_human_review: bool = Field(
        False,
        description="Whether the claim is waiting for human review"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if any"
    )


class PendingReviewItem(BaseModel):
    """Item in pending reviews list."""

    claim_id: str = Field(
        ...,
        description="Claim identifier"
    )
    policy_number: str = Field(
        ...,
        description="Policy number for the claim"
    )
    agent_1_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Completeness check result"
    )
    agent_2_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Quality check result"
    )
    submitted_at: Optional[str] = Field(
        None,
        description="When the claim was submitted for review"
    )


class PendingReviewsResponse(BaseModel):
    """Response for pending reviews endpoint."""

    reviews: List[PendingReviewItem] = Field(
        default_factory=list,
        description="List of claims waiting for human review"
    )
    count: int = Field(
        ...,
        description="Number of pending reviews"
    )


class SubmitReviewRequest(BaseModel):
    """Request for submitting human review."""

    decision: Literal["approve", "reject", "edit"] = Field(
        ...,
        description="Human decision: approve, reject, or edit"
    )
    feedback: str = Field(
        ...,
        description="Human feedback and reasoning"
    )
    reviewed_by: str = Field(
        default="human_reviewer",
        description="Identifier of the reviewer"
    )
    edited_agent_1_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Human-edited version of Agent 1 result"
    )
    edited_agent_2_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Human-edited version of Agent 2 result"
    )


class SubmitReviewResponse(BaseModel):
    """Response for submitting human review."""

    claim_id: str = Field(
        ...,
        description="Claim identifier"
    )
    status: str = Field(
        ...,
        description="Status after submission"
    )
    message: str = Field(
        ...,
        description="Human-readable status message"
    )
