"""Functional accuracy metrics for claim decisions."""

from __future__ import annotations

from typing import TypedDict


class AccuracyResult(TypedDict):
    """Result container for accuracy metrics."""

    accuracy: float
    f1_macro: float
    f1_weighted: float
    precision_macro: float
    recall_macro: float
    f1_per_category: dict[str, float]
    confusion_matrix: list[list[int]]


def compute_f1_scores(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
) -> AccuracyResult:
    """Compute F1, precision, recall for accept/reject classification.

    Args:
        y_true: Ground truth decisions (accept/reject/needs_review).
        y_pred: Predicted decisions from agent.
        labels: Optional list of label ordering for confusion matrix.

    Returns:
        AccuracyResult dict with metrics.
    """
    labels = labels or ["accept", "reject", "needs_review"]

    per_label_scores = {
        label: _precision_recall_f1_for_label(y_true, y_pred, label) for label in labels
    }
    support = {label: sum(1 for item in y_true if item == label) for label in labels}
    total_support = sum(support.values())

    result: AccuracyResult = {
        "accuracy": _accuracy_score(y_true, y_pred),
        "f1_macro": _mean([scores["f1"] for scores in per_label_scores.values()]),
        "f1_weighted": (
            sum(per_label_scores[label]["f1"] * support[label] for label in labels) / total_support
            if total_support
            else 0.0
        ),
        "precision_macro": _mean([scores["precision"] for scores in per_label_scores.values()]),
        "recall_macro": _mean([scores["recall"] for scores in per_label_scores.values()]),
        "f1_per_category": {},
        "confusion_matrix": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
    }

    result["confusion_matrix"], _ = compute_confusion_matrix(y_true, y_pred, labels)
    for label in labels:
        result["f1_per_category"][label] = per_label_scores[label]["f1"]

    return result


def compute_confusion_matrix(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
) -> tuple[list[list[int]], list[str]]:
    """Compute confusion matrix for claim decisions.

    Returns:
        Tuple of (matrix, labels) for sklearn ConfusionMatrixDisplay.
    """
    labels = labels or ["accept", "reject", "needs_review"]
    matrix = [[0 for _ in labels] for _ in labels]

    label_to_idx = {label: i for i, label in enumerate(labels)}
    for true, pred in zip(y_true, y_pred, strict=False):
        if true in label_to_idx and pred in label_to_idx:
            matrix[label_to_idx[true]][label_to_idx[pred]] += 1

    return matrix, labels


def compute_completeness_accuracy(
    expected_missing: list[list[str]],
    detected_missing: list[list[str]],
) -> dict[str, float]:
    """Compute completeness detection accuracy.

    Args:
        expected_missing: List of expected missing documents per claim.
        detected_missing: List of detected missing documents per claim.

    Returns:
        Dict with precision, recall, f1 for missing document detection.
    """
    tp, fp, fn = 0, 0, 0

    for expected, detected in zip(expected_missing, detected_missing, strict=False):
        expected_set = set(expected)
        detected_set = set(detected)

        tp += len(expected_set & detected_set)
        fp += len(detected_set - expected_set)
        fn += len(expected_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def compute_set_f1(
    expected_items: list[list[str]],
    detected_items: list[list[str]],
) -> dict[str, float]:
    """Compute micro precision/recall/F1 for list-valued labels."""
    tp, fp, fn = 0, 0, 0

    for expected, detected in zip(expected_items, detected_items, strict=False):
        expected_set = set(expected)
        detected_set = set(detected)
        tp += len(expected_set & detected_set)
        fp += len(detected_set - expected_set)
        fn += len(expected_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def generate_classification_report(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
) -> str:
    """Generate sklearn classification report as string."""
    labels = labels or ["accept", "reject", "needs_review"]
    lines = ["label,precision,recall,f1,support"]
    for label in labels:
        scores = _precision_recall_f1_for_label(y_true, y_pred, label)
        support = sum(1 for item in y_true if item == label)
        lines.append(
            f"{label},{scores['precision']:.4f},{scores['recall']:.4f},{scores['f1']:.4f},{support}"
        )
    return "\n".join(lines)


def _accuracy_score(y_true: list[str], y_pred: list[str]) -> float:
    if not y_true:
        return 0.0
    correct = sum(1 for true, pred in zip(y_true, y_pred, strict=False) if true == pred)
    return correct / len(y_true)


def _precision_recall_f1_for_label(
    y_true: list[str],
    y_pred: list[str],
    label: str,
) -> dict[str, float]:
    tp = sum(
        1 for true, pred in zip(y_true, y_pred, strict=False) if true == label and pred == label
    )
    fp = sum(
        1 for true, pred in zip(y_true, y_pred, strict=False) if true != label and pred == label
    )
    fn = sum(
        1 for true, pred in zip(y_true, y_pred, strict=False) if true == label and pred != label
    )
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
