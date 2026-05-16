"""One entrypoint for evaluation workflows.

Examples:
    python -m eval run --skip-existing --build-suggestions
    python -m eval metrics --multi-results eval/results/claims
    python -m eval label-ui
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval import baseline, batch_run, reference_labels
from eval.ground_truth import clean_ground_truth_file
from eval.paths import (
    AGENT_SUGGESTIONS,
    CLAIM_RESULTS_DIR,
    CLAIM_SUGGESTIONS_DIR,
    GROUND_TRUTH,
    HISTORY,
    RESULTS_DIR,
)
from eval.runner import summarize, write_agent_suggestions

DEFAULT_BASE_URL = batch_run.DEFAULT_BASE_URL


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        _run_batch(args)
    elif args.command == "metrics":
        multi_results = args.multi_results if args.multi_results.exists() else None
        summary = summarize(
            args.ground_truth,
            multi_results,
            args.single_results,
            args.output_dir,
            args.labels,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "suggestions":
        rows = write_agent_suggestions(
            args.results,
            args.output,
            args.mode,
            suggestions_dir=args.suggestions_dir,
        )
        print(f"Wrote {len(rows)} suggestions: {args.output}")
    elif args.command == "clean-ground-truth":
        stats = clean_ground_truth_file(args.ground_truth, args.output)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif args.command == "run-baseline":
        results = baseline.run_baseline(args)
        if not args.dry_run:
            print(f"Wrote {len(results)} baseline results: {args.results_dir}")
    elif args.command == "label-reference":
        payload = reference_labels.run_label_reference(args)
        if not args.dry_run:
            print(f"Wrote {len(payload.get('labels', []))} reference labels: {args.output}")
    elif args.command == "label-ui":
        _run_label_ui(args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Thesis evaluation toolkit.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run claims through the multi-agent API.")
    run.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    run.add_argument("--results-dir", type=Path, default=CLAIM_RESULTS_DIR)
    run.add_argument("--suggestions", type=Path, default=AGENT_SUGGESTIONS)
    run.add_argument("--suggestions-dir", type=Path, default=CLAIM_SUGGESTIONS_DIR)
    run.add_argument("--history", type=Path, default=HISTORY)
    run.add_argument("--base-url", default=DEFAULT_BASE_URL)
    run.add_argument("--timeout", type=float, default=900.0)
    run.add_argument("--limit", type=int)
    run.add_argument("--claim-id", action="append")
    run.add_argument(
        "--no-upload",
        dest="deprecated_no_upload",
        action="store_true",
        help=(
            "Deprecated no-op. Current agent-service requires workflow inputs under "
            "UPLOADS_DIR, so eval uploads documents before running workflows."
        ),
    )
    run.add_argument("--skip-existing", action="store_true")
    run.add_argument("--fail-fast", action="store_true")
    run.add_argument("--build-suggestions", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(upload=True, deprecated_no_upload=False)

    metrics = subparsers.add_parser("metrics", help="Compute metrics from saved results.")
    metrics.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    metrics.add_argument("--labels", type=Path)
    metrics.add_argument("--multi-results", type=Path, default=CLAIM_RESULTS_DIR)
    metrics.add_argument("--single-results", type=Path)
    metrics.add_argument("--output-dir", type=Path, default=RESULTS_DIR)

    suggestions = subparsers.add_parser("suggestions", help="Build labeling suggestions.")
    suggestions.add_argument("--results", type=Path, default=CLAIM_RESULTS_DIR)
    suggestions.add_argument("--output", type=Path, default=AGENT_SUGGESTIONS)
    suggestions.add_argument("--suggestions-dir", type=Path, default=CLAIM_SUGGESTIONS_DIR)
    suggestions.add_argument("--mode", default="multi_agent")

    label_ui = subparsers.add_parser("label-ui", help="Open the Streamlit labeling UI.")
    label_ui.add_argument("--port", type=int, default=8502)

    clean = subparsers.add_parser(
        "clean-ground-truth",
        help="Remove temporary fake labels from the dataset manifest.",
    )
    clean.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    clean.add_argument("--output", type=Path)

    run_baseline = subparsers.add_parser(
        "run-baseline",
        help="Run the single-agent baseline for RQ5.",
        parents=[baseline.build_parser(add_help=False)],
    )
    run_baseline.set_defaults(command="run-baseline")

    label_reference = subparsers.add_parser(
        "label-reference",
        help="Draft LLM-assisted reference labels with Gemini 3.1 Pro preview.",
        parents=[reference_labels.build_parser(add_help=False)],
    )
    label_reference.set_defaults(command="label-reference")

    return parser


def _run_batch(args: argparse.Namespace) -> None:
    results = batch_run.run_batch(args)
    if not args.dry_run:
        print(f"Wrote {len(results)} results: {args.results_dir}")


def _run_label_ui(port: int) -> None:
    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        "eval/labeling_app.py",
        "--server.port",
        str(port),
    ]
    streamlit_cli.main()


if __name__ == "__main__":
    main()
