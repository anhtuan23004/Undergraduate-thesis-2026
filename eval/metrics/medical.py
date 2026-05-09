"""Medical knowledge validation metrics (ICD codes, medications, exclusions)."""

from __future__ import annotations

from typing import TypedDict

from .accuracy import compute_set_f1


class MedicalResult(TypedDict):
    """Result container for medical metrics."""

    icd_accuracy: float
    icd_precision: float
    icd_recall: float
    medication_recall: float
    medication_precision: float
    exclusion_precision: float
    exclusion_recall: float


def compute_icd_accuracy(
    expected_icd: list[list[str]],
    detected_icd: list[list[str]],
) -> MedicalResult:
    """Compute ICD-10 code detection accuracy.

    Args:
        expected_icd: List of expected ICD codes per claim.
        detected_icd: List of detected ICD codes per claim.

    Returns:
        MedicalResult with accuracy, precision, recall.
    """
    tp, fp, fn = 0, 0, 0

    for expected, detected in zip(expected_icd, detected_icd, strict=False):
        expected_set = set(expected)
        detected_set = set(detected)

        tp += len(expected_set & detected_set)
        fp += len(detected_set - expected_set)
        fn += len(expected_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0

    return {
        "icd_accuracy": accuracy,
        "icd_precision": precision,
        "icd_recall": recall,
        "medication_recall": 0.0,
        "medication_precision": 0.0,
        "exclusion_precision": 0.0,
        "exclusion_recall": 0.0,
    }


def compute_medication_recall(
    expected_meds: list[list[str]],
    detected_meds: list[list[str]],
) -> tuple[float, float]:
    """Compute medication detection precision and recall.

    Returns:
        Tuple of (precision, recall).
    """
    tp, fp, fn = 0, 0, 0

    for expected, detected in zip(expected_meds, detected_meds, strict=False):
        expected_set = set(expected)
        detected_set = set(detected)

        tp += len(expected_set & detected_set)
        fp += len(detected_set - expected_set)
        fn += len(expected_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return precision, recall


def compute_exclusion_detection(
    expected_exclusions: list[list[str]],
    detected_exclusions: list[list[str]],
) -> tuple[float, float]:
    """Compute policy exclusion detection precision and recall.

    Returns:
        Tuple of (precision, recall).
    """
    tp, fp, fn = 0, 0, 0

    for expected, detected in zip(expected_exclusions, detected_exclusions, strict=False):
        expected_set = set(expected)
        detected_set = set(detected)

        tp += len(expected_set & detected_set)
        fp += len(detected_set - expected_set)
        fn += len(expected_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return precision, recall


def compute_quality_issue_detection(
    expected_issues: list[list[str]],
    detected_issues: list[list[str]],
) -> dict[str, float]:
    """Compute quality issue detection precision/recall/F1."""
    return compute_set_f1(expected_issues, detected_issues)
