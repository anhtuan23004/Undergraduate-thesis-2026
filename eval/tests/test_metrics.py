from eval.metrics import (
    compute_completeness_accuracy,
    compute_f1_scores,
    compute_path_accuracy,
    compute_tool_f1,
)


def test_tool_f1_uses_intersection():
    result = compute_tool_f1(
        expected_tools=[["check-required-docs", "validate-consistency"]],
        called_tools=[["check-required-docs", "web-search"]],
    )

    assert result == {"precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_completeness_f1_for_missing_documents():
    result = compute_completeness_accuracy(
        expected_missing=[["invoice"], ["discharge-paper"]],
        detected_missing=[["invoice"], ["invoice"]],
    )

    assert result == {"precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_routing_path_accuracy_exact_match():
    accuracy = compute_path_accuracy(
        expected_paths=[["completeness_check", "quality_check"], ["completeness_check"]],
        actual_paths=[["completeness_check", "quality_check"], ["quality_check"]],
    )

    assert accuracy == 0.5


def test_decision_f1_accept_reject_needs_review():
    result = compute_f1_scores(
        y_true=["accept", "reject", "needs_review"],
        y_pred=["accept", "needs_review", "needs_review"],
    )

    assert result["accuracy"] == 2 / 3
    assert set(result["f1_per_category"]) == {"accept", "reject", "needs_review"}
