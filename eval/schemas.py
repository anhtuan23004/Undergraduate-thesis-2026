"""Shared schemas and normalization helpers for thesis experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DEFAULT_EXPECTED_TOOLS: dict[str, list[str]] = {
    "CompletenessAgent": ["classify-benefit", "check-required-docs", "validate-consistency"],
    "QualityAgent": [
        "check-icd",
        "check-exclusion",
        "validate-medication",
        "search-medicine",
        "web-search",
    ],
    "DecisionAgent": ["aggregate-issues"],
}

DecisionLabel = Literal["accept", "reject", "needs_review"]
RunMode = Literal["multi_agent", "single_agent"]


@dataclass
class ExperimentResult:
    """Normalized result row for one claim and one experiment mode."""

    claim_id: str
    mode: RunMode
    agent_outputs: dict[str, Any] = field(default_factory=dict)
    final_decision: str = ""
    routing_path: list[str] = field(default_factory=list)
    called_tools_by_agent: dict[str, list[str]] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    token_usage: int = 0
    langfuse_trace_id: str = ""
    human_reviewed: bool = False
    human_override: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_final_decision(raw_decision: str | None) -> str:
    """Normalize final decision labels across agent and thesis terminology."""
    if not raw_decision:
        return ""
    value = raw_decision.strip().lower()
    mapping = {
        "approve": "accept",
        "approved": "accept",
        "accept": "accept",
        "reject": "reject",
        "rejected": "reject",
        "need_more_info": "needs_review",
        "needs_review": "needs_review",
        "accept_with_edit": "needs_review",
        "review": "needs_review",
    }
    return mapping.get(value, value)


def get_expected_tools(claim: dict[str, Any]) -> dict[str, list[str]]:
    """Return claim-level expected tools, falling back to the thesis default."""
    configured = claim.get("expected_tools_by_agent")
    if isinstance(configured, dict) and configured:
        return {agent: list(tools) for agent, tools in configured.items()}
    return {agent: list(tools) for agent, tools in DEFAULT_EXPECTED_TOOLS.items()}
