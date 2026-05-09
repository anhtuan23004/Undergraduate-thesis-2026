"""Evaluation metrics for agentic LLM insurance claims processing."""

from .accuracy import (
    compute_completeness_accuracy,
    compute_confusion_matrix,
    compute_f1_scores,
    compute_set_f1,
)
from .agent_behavior import (
    compute_error_recovery_rate,
    compute_invalid_tool_call_rate,
    compute_path_accuracy,
    compute_routing_accuracy,
    compute_routing_transition_matrix,
    compute_self_correction_rate,
    compute_tool_f1,
    compute_tool_failure_rate,
    compute_tool_precision,
    compute_tool_recall,
    compute_trace_completeness,
)
from .human_factor import (
    compute_human_agreement,
    compute_human_review_rate,
    compute_override_rate,
    compute_time_savings,
)
from .medical import (
    compute_exclusion_detection,
    compute_icd_accuracy,
    compute_medication_recall,
    compute_quality_issue_detection,
)
from .performance import compute_latency_percentiles, compute_throughput, compute_token_cost

__all__ = [
    "compute_f1_scores",
    "compute_confusion_matrix",
    "compute_completeness_accuracy",
    "compute_set_f1",
    "compute_tool_precision",
    "compute_tool_recall",
    "compute_tool_f1",
    "compute_invalid_tool_call_rate",
    "compute_tool_failure_rate",
    "compute_routing_accuracy",
    "compute_path_accuracy",
    "compute_trace_completeness",
    "compute_self_correction_rate",
    "compute_error_recovery_rate",
    "compute_routing_transition_matrix",
    "compute_icd_accuracy",
    "compute_medication_recall",
    "compute_exclusion_detection",
    "compute_quality_issue_detection",
    "compute_latency_percentiles",
    "compute_token_cost",
    "compute_throughput",
    "compute_override_rate",
    "compute_human_review_rate",
    "compute_human_agreement",
    "compute_time_savings",
]
