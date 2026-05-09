"""Human-in-the-loop interaction metrics."""

from __future__ import annotations

from typing import TypedDict


class HumanFactorResult(TypedDict):
    """Result container for human factor metrics."""

    override_rate: float
    override_rate_by_stage: dict[str, float]
    human_agreement_rate: float
    time_savings_minutes: float
    avg_review_time_minutes: float


def compute_override_rate(
    total_claims: int,
    overridden_claims: int,
) -> float:
    """Compute overall human override rate.

    Args:
        total_claims: Total number of claims processed.
        overridden_claims: Number of claims with human overrides.

    Returns:
        Override rate (0.0 to 1.0).
    """
    return overridden_claims / total_claims if total_claims > 0 else 0.0


def compute_human_review_rate(
    total_claims: int,
    reviewed_claims: int,
) -> float:
    """Compute the fraction of claims routed to human review."""
    return reviewed_claims / total_claims if total_claims > 0 else 0.0


def compute_override_rate_by_stage(
    stage_overrides: dict[str, int],
    stage_totals: dict[str, int],
) -> dict[str, float]:
    """Compute override rate per workflow stage.

    Args:
        stage_overrides: Dict mapping stage to override count.
        stage_totals: Dict mapping stage to total claims.

    Returns:
        Dict mapping stage to override rate.
    """
    return {
        stage: stage_overrides.get(stage, 0) / stage_totals.get(stage, 1) for stage in stage_totals
    }


def compute_human_agreement(
    agent_decisions: list[str],
    human_decisions: list[str],
) -> float:
    """Compute human-agent agreement rate.

    Args:
        agent_decisions: List of agent decisions per claim.
        human_decisions: List of final human decisions per claim.

    Returns:
        Agreement rate (0.0 to 1.0).
    """
    if len(agent_decisions) != len(human_decisions):
        raise ValueError("Lists must have same length")

    agreements = sum(1 for a, h in zip(agent_decisions, human_decisions, strict=False) if a == h)
    return agreements / len(agent_decisions) if agent_decisions else 0.0


def compute_time_savings(
    human_only_times_minutes: list[float],
    agent_assisted_times_minutes: list[float],
) -> tuple[float, float]:
    """Compute time savings from agent assistance.

    Args:
        human_only_times_minutes: Time for human-only processing.
        agent_assisted_times_minutes: Time with agent assistance.

    Returns:
        Tuple of (avg_savings_minutes, total_savings_minutes).
    """
    if len(human_only_times_minutes) != len(agent_assisted_times_minutes):
        raise ValueError("Lists must have same length")

    savings = [
        h - a for h, a in zip(human_only_times_minutes, agent_assisted_times_minutes, strict=False)
    ]
    avg_savings = sum(savings) / len(savings) if savings else 0.0
    total_savings = sum(s for s in savings if s > 0)

    return avg_savings, total_savings


def compute_avg_review_time(
    review_times_minutes: list[float],
) -> float:
    """Compute average human review time per claim.

    Args:
        review_times_minutes: List of review times in minutes.

    Returns:
        Average review time in minutes.
    """
    return sum(review_times_minutes) / len(review_times_minutes) if review_times_minutes else 0.0
