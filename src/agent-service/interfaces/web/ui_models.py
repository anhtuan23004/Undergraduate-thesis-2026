"""UI data models for the Streamlit interface."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Issue:
    """Represents an issue found during claim processing."""

    severity: str
    description: str
    field: Optional[str] = None


@dataclass
class AgentResult:
    """Represents the result from an agent's processing."""

    decision: str
    confidence: float
    reasoning: str
    missing_documents: Optional[List[str]] = None
    issues: Optional[List[Dict[str, Any]]] = None


@dataclass
class ProcessingStep:
    """Represents a step in the processing history."""

    step: str
    status: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None
