"""LangGraph workflow definitions."""

from workflow.contracts import GraphState

__all__ = ["GraphState", "build_claim_workflow"]


def __getattr__(name: str):
    """Lazily expose workflow builder without creating import cycles."""
    if name == "build_claim_workflow":
        from graphs.claim_workflow import build_claim_workflow

        return build_claim_workflow
    raise AttributeError(name)
