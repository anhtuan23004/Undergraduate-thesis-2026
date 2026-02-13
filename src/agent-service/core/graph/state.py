"""State definition for ReAct agent graph."""
from typing import Annotated, Any, Dict, List, Optional, TypedDict

import operator


class AgentState(TypedDict):
    """State for the ReAct agent.

    This state is passed between nodes in the LangGraph.
    Each field represents a piece of the agent's working memory.
    """

    # === Input Data ===
    claim_id: str
    extracted_data: Dict[str, Any]
    policy_number: str
    submission_date: Optional[str]

    # === ReAct Loop ===
    observations: Annotated[List[str], operator.add]
    thoughts: Annotated[List[str], operator.add]
    actions: Annotated[List[Dict[str, Any]], operator.add]
    reflections: Annotated[List[str], operator.add]

    # === Context ===
    retrieved_context: List[Dict[str, Any]]
    tool_results: Annotated[List[Dict[str, Any]], operator.add]

    # === Output ===
    decision: Optional[str]
    confidence_score: float
    amount_recommended: float
    reasoning: str
    evidence: List[Dict[str, Any]]
    risks: List[str]

    # === Control ===
    iteration_count: int
    max_iterations: int
    should_continue: bool
    error: Optional[str]


def create_initial_state(
    claim_id: str,
    extracted_data: Dict[str, Any],
    policy_number: str,
    submission_date: Optional[str] = None,
    max_iterations: int = 10
) -> AgentState:
    """Create initial state for a new claim processing."""
    return {
        "claim_id": claim_id,
        "extracted_data": extracted_data,
        "policy_number": policy_number,
        "submission_date": submission_date,
        "observations": [],
        "thoughts": [],
        "actions": [],
        "reflections": [],
        "retrieved_context": [],
        "tool_results": [],
        "decision": None,
        "confidence_score": 0.0,
        "amount_recommended": 0.0,
        "reasoning": "",
        "evidence": [],
        "risks": [],
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "should_continue": True,
        "error": None
    }
