"""Pydantic models for multi-agent API."""
from typing import List, Dict, Any, Optional, Literal

from pydantic import BaseModel, Field


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
        description="Path to the input file"
    )
    policy_number: str = Field(
        ...,
        description="Policy number for the claim"
    )


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
