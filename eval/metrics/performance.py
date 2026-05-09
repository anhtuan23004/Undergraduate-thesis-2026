"""System performance metrics (latency, cost, throughput)."""

from __future__ import annotations

from typing import TypedDict

import numpy as np


class PerformanceResult(TypedDict):
    """Result container for performance metrics."""

    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_mean_ms: float
    token_cost_per_claim: float
    total_tokens: int
    throughput_claims_per_hour: float


def compute_latency_percentiles(
    processing_times_ms: list[float],
) -> PerformanceResult:
    """Compute latency percentiles from processing times.

    Args:
        processing_times_ms: List of processing times in milliseconds.

    Returns:
        PerformanceResult with percentiles.
    """
    if not processing_times_ms:
        return {
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "latency_p99_ms": 0.0,
            "latency_mean_ms": 0.0,
            "token_cost_per_claim": 0.0,
            "total_tokens": 0,
            "throughput_claims_per_hour": 0.0,
        }

    times = np.array(processing_times_ms)

    return {
        "latency_p50_ms": float(np.percentile(times, 50)),
        "latency_p95_ms": float(np.percentile(times, 95)),
        "latency_p99_ms": float(np.percentile(times, 99)),
        "latency_mean_ms": float(np.mean(times)),
        "token_cost_per_claim": 0.0,
        "total_tokens": 0,
        "throughput_claims_per_hour": 0.0,
    }


def compute_token_cost(
    token_counts: list[int],
    cost_per_token: float = 0.0,
) -> tuple[float, int]:
    """Compute average token cost per claim.

    Args:
        token_counts: List of token counts per claim.
        cost_per_token: Cost per token in USD (default Gemini 2.0 flash).

    Returns:
        Tuple of (average_cost, total_tokens).
    """
    total = sum(token_counts)
    avg_cost = (total * cost_per_token) / len(token_counts) if token_counts else 0.0

    return avg_cost, total


def compute_throughput(
    claim_count: int,
    total_time_seconds: float,
) -> float:
    """Compute throughput in claims per hour.

    Args:
        claim_count: Number of claims processed.
        total_time_seconds: Total processing time in seconds.

    Returns:
        Claims per hour.
    """
    hours = total_time_seconds / 3600.0
    return claim_count / hours if hours > 0 else 0.0


def compute_stage_latency(
    stage_times: dict[str, list[float]],
) -> dict[str, dict[str, float]]:
    """Compute latency statistics per workflow stage.

    Args:
        stage_times: Dict mapping stage names to lists of times.

    Returns:
        Dict mapping stage names to percentile dicts.
    """
    result = {}
    for stage, times in stage_times.items():
        if not times:
            continue
        arr = np.array(times)
        result[stage] = {
            "p50_ms": float(np.percentile(arr, 50)),
            "p95_ms": float(np.percentile(arr, 95)),
            "p99_ms": float(np.percentile(arr, 99)),
            "mean_ms": float(np.mean(arr)),
        }
    return result
