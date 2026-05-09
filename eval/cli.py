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

from eval import batch_run
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
    run.add_argument("--no-upload", dest="upload", action="store_false")
    run.add_argument("--skip-existing", action="store_true")
    run.add_argument("--fail-fast", action="store_true")
    run.add_argument("--build-suggestions", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(upload=True)

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
