"""Shared paths for evaluation utilities."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
DATASET_DIR = EVAL_DIR / "dataset"
RESULTS_DIR = EVAL_DIR / "results"
REPORT_FIGURES_DIR = EVAL_DIR / "reports" / "figures"

GROUND_TRUTH = DATASET_DIR / "ground_truth.json"
CLAIM_RESULTS_DIR = RESULTS_DIR / "claims"
CLAIM_SUGGESTIONS_DIR = RESULTS_DIR / "suggestions"
AGENT_SUGGESTIONS = RESULTS_DIR / "agent_suggestions.json"
REVIEWED_LABELS = RESULTS_DIR / "reviewed_labels.json"
HISTORY = RESULTS_DIR / "history.json"
