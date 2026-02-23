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
        resolved = (uploads_dir / v).resolve()

        # Ensure the resolved path is still inside uploads_dir
        try:
            resolved.relative_to(uploads_dir)
        except ValueError:
            raise ValueError("input_file must resolve to a path within the uploads directory")

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
