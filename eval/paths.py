"""Shared paths for evaluation utilities."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
DATASET_DIR = EVAL_DIR / "dataset"
RESULTS_DIR = EVAL_DIR / "results"
REPORTS_DIR = EVAL_DIR / "reports"
REPORT_FIGURES_DIR = REPORTS_DIR / "figures"

GROUND_TRUTH = DATASET_DIR / "ground_truth.json"
CLAIM_RESULTS_DIR = RESULTS_DIR / "claims"
SINGLE_AGENT_RESULTS_DIR = RESULTS_DIR / "single_agent_claims"
CLAIM_SUGGESTIONS_DIR = RESULTS_DIR / "suggestions"
OCR_CACHE_DIR = RESULTS_DIR / "ocr_cache"
AGENT_SUGGESTIONS = RESULTS_DIR / "agent_suggestions.json"
REVIEWED_LABELS = RESULTS_DIR / "reviewed_labels.json"
AUDIT_QUEUE = RESULTS_DIR / "audit_queue.csv"
HISTORY = RESULTS_DIR / "history.json"
RQ_REPORT = REPORTS_DIR / "rq_report.md"
