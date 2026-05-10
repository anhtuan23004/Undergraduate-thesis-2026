"""Pydantic schemas for API request/response models."""

from typing import Literal

from pydantic import BaseModel, Field


class ClaimRequest(BaseModel):
    """Request model for claim processing."""

    claim_id: str = Field(..., description="Claim identifier")
    policy_number: str = Field(..., description="Policy number")
    input_file: str = Field(
        ...,
        description=(
            "Path to input document. Relative paths are resolved under UPLOADS_DIR; "
            "absolute paths must also point inside UPLOADS_DIR."
        ),
    )
    file_hash: str | None = Field(None, description="SHA-256 hash of the document")


class HumanReviewRequest(BaseModel):
    """Request model for human review decision."""

    decision: Literal["approve", "reject", "edit"] = Field(
        ..., description="Decision: approve, reject, or edit"
    )
    notes: str | None = Field(default=None, description="Reviewer notes")
    edited_result: dict | None = Field(
        default=None, description="Edited agent result if decision is edit"
    )


class ContinueRequest(BaseModel):
    """Request model for continuing a paused workflow stage."""

    note: str | None = Field(default=None, description="Optional note for audit trail")


class UploadResponse(BaseModel):
    """Response model for uploaded documents."""

    filename: str
    file_path: str
    size_bytes: int
    file_hash: str


class WorkflowErrorResponse(BaseModel):
    """Standardized error response shape for workflow endpoints."""

    error: str = Field(description="Human-readable error message")
    error_detail: str | None = Field(default=None, description="Technical detail")
    status_code: int = Field(description="HTTP status code")
    endpoint: str | None = Field(default=None, description="Originating endpoint")
