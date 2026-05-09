"""Agent behavior metrics (tool usage, routing, self-correction)."""

from __future__ import annotations

from collections import defaultdict
from typing import TypedDict


class AgentBehaviorResult(TypedDict):
    """Result container for agent behavior metrics."""

    tool_call_precision: float
    tool_call_recall: float
    routing_accuracy: float
    routing_transition_matrix: dict[str, dict[str, int]]
    self_correction_rate: float
    error_recovery_rate: float
    invalid_tool_call_rate: float
    tool_failure_rate: float
    trace_completeness: float


def compute_tool_precision(
    expected_tools: list[list[str]],
    called_tools: list[list[str]],
) -> float:
    """Compute tool call precision - fraction of called tools that were needed.

    Args:
        expected_tools: List of sets of tools that should have been called.
        called_tools: List of sets of tools actually called by agent.

    Returns:
        Precision score (0.0 to 1.0).
    """
    total_correct = 0
    total_called = 0

    for expected, called in zip(expected_tools, called_tools, strict=False):
        expected_set = set(expected)
        called_set = set(called)

        total_correct += len(expected_set & called_set)
        total_called += len(called_set)

    return total_correct / total_called if total_called > 0 else 0.0


def compute_tool_recall(
    expected_tools: list[list[str]],
    called_tools: list[list[str]],
) -> float:
    """Compute tool call recall - fraction of needed tools that were called.

    Args:
        expected_tools: List of sets of tools that should have been called.
        called_tools: List of sets of tools actually called by agent.

    Returns:
        Recall score (0.0 to 1.0).
    """
    total_expected = 0
    total_found = 0

    for expected, called in zip(expected_tools, called_tools, strict=False):
        expected_set = set(expected)
        called_set = set(called)

        total_expected += len(expected_set)
        total_found += len(expected_set & called_set)

    return total_found / total_expected if total_expected > 0 else 0.0


def compute_tool_f1(
    expected_tools: list[list[str]],
    called_tools: list[list[str]],
) -> dict[str, float]:
    """Compute precision/recall/F1 for tool usage."""
    precision = compute_tool_precision(expected_tools, called_tools)
    recall = compute_tool_recall(expected_tools, called_tools)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def compute_invalid_tool_call_rate(
    expected_tools: list[list[str]],
    called_tools: list[list[str]],
) -> float:
    """Compute the fraction of tool calls that were not expected."""
    invalid = 0
    total_called = 0
    for expected, called in zip(expected_tools, called_tools, strict=False):
        expected_set = set(expected)
        called_set = set(called)
        invalid += len(called_set - expected_set)
        total_called += len(called_set)
    return invalid / total_called if total_called else 0.0


def compute_tool_failure_rate(tool_results: list[dict]) -> float:
    """Compute the fraction of observed tool calls that failed."""
    if not tool_results:
        return 0.0
    failures = sum(1 for result in tool_results if result.get("status") == "error")
    return failures / len(tool_results)


def compute_routing_accuracy(
    expected_transitions: list[tuple[str, str]],
    actual_transitions: list[tuple[str, str]],
) -> float:
    """Compute routing accuracy - fraction of correct state transitions.

    Args:
        expected_transitions: List of (from_state, to_state) tuples.
        actual_transitions: List of observed transitions.

    Returns:
        Accuracy score (0.0 to 1.0).
    """
    expected_set = set(expected_transitions)
    actual_set = set(actual_transitions)

    correct = len(expected_set & actual_set)
    total = len(actual_set) if actual_set else len(expected_set)

    return correct / total if total > 0 else 0.0


def compute_path_accuracy(
    expected_paths: list[list[str]],
    actual_paths: list[list[str]],
) -> float:
    """Compute exact-match routing path accuracy per claim."""
    if not expected_paths:
        return 0.0
    matches = sum(
        1
        for expected, actual in zip(expected_paths, actual_paths, strict=False)
        if expected == actual
    )
    return matches / len(expected_paths)


def compute_trace_completeness(
    traces: list[dict],
    required_fields: list[str] | None = None,
) -> float:
    """Compute average completeness over required trace fields."""
    required_fields = required_fields or [
        "claim_id",
        "mode",
        "agent_outputs",
        "final_decision",
        "routing_path",
        "called_tools_by_agent",
        "latency_ms",
        "token_usage",
    ]
    if not traces:
        return 0.0

    scores = []
    for trace in traces:
        present = sum(1 for field in required_fields if trace.get(field) not in (None, "", [], {}))
        scores.append(present / len(required_fields))
    return sum(scores) / len(scores)


def compute_routing_transition_matrix(
    transitions: list[tuple[str, str]],
) -> dict[str, dict[str, int]]:
    """Build transition matrix from state pairs.

    Returns:
        Dict[from_state, Dict[to_state, count]].
    """
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for from_state, to_state in transitions:
        matrix[from_state][to_state] += 1

    return {k: dict(v) for k, v in matrix.items()}


def compute_self_correction_rate(
    correction_count: list[int],
    total_attempts: list[int],
) -> float:
    """Compute self-correction rate per claim.

    Args:
        correction_count: Number of self-corrections per claim.
        total_attempts: Number of total attempts per claim.

    Returns:
        Correction rate (0.0 to 1.0).
    """
    total_corrections = sum(correction_count)
    total = sum(total_attempts)

    return total_corrections / total if total > 0 else 0.0


def compute_error_recovery_rate(
    error_count: list[int],
    recovery_count: list[int],
) -> float:
    """Compute error recovery rate.

    Args:
        error_count: Number of errors per claim.
        recovery_count: Number of successful recoveries per claim.

    Returns:
        Recovery rate (0.0 to 1.0).
    """
    total_errors = sum(error_count)
    total_recoveries = sum(recovery_count)

    return total_recoveries / total_errors if total_errors > 0 else 0.0
