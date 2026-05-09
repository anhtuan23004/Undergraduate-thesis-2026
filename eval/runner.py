"""Evaluation runner for Chapter 4 experiments.

This runner aggregates normalized experiment outputs and computes metrics. Live
LLM/OCR execution is deliberately optional; the default path is reproducible and
uses cached OCR plus saved result files.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from eval.metrics import (
    compute_completeness_accuracy,
    compute_f1_scores,
    compute_human_review_rate,
    compute_invalid_tool_call_rate,
    compute_latency_percentiles,
    compute_path_accuracy,
    compute_set_f1,
    compute_tool_f1,
    compute_tool_failure_rate,
    compute_trace_completeness,
)
from eval.paths import (
    AGENT_SUGGESTIONS,
    CLAIM_SUGGESTIONS_DIR,
    GROUND_TRUTH,
    REPORT_FIGURES_DIR,
    RESULTS_DIR,
)
from eval.schemas import ExperimentResult, get_expected_tools, normalize_final_decision

DEFAULT_GROUND_TRUTH = GROUND_TRUTH
DEFAULT_RESULTS_DIR = RESULTS_DIR
DEFAULT_REPORT_FIGURES_DIR = REPORT_FIGURES_DIR
DEFAULT_SUGGESTIONS = AGENT_SUGGESTIONS
DEFAULT_SUGGESTIONS_DIR = CLAIM_SUGGESTIONS_DIR


def load_ground_truth(path: Path = DEFAULT_GROUND_TRUTH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_reviewed_labels(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("labels", [])
    return {str(row["claim_id"]): row for row in rows if row.get("claim_id")}


def load_results(path: Path) -> list[ExperimentResult]:
    if not path.exists():
        return []
    if path.is_dir():
        return [
            ExperimentResult(**json.loads(result_path.read_text(encoding="utf-8")))
            for result_path in sorted(path.glob("*.json"))
        ]
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            rows = csv.DictReader(handle)
            return [_result_from_csv_row(row) for row in rows]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [ExperimentResult(**row) for row in payload]
    if "results" in payload:
        return [ExperimentResult(**row) for row in payload.get("results", [])]
    return [ExperimentResult(**payload)]


def _result_from_csv_row(row: dict[str, str]) -> ExperimentResult:
    return ExperimentResult(
        claim_id=row.get("claim_id", ""),
        mode=row.get("mode", "multi_agent") or "multi_agent",
        final_decision=row.get("final_decision", ""),
        routing_path=_json_list(row.get("routing_path", "")),
        called_tools_by_agent=_json_dict(row.get("called_tools_by_agent", "")),
        latency_ms=float(row.get("latency_ms") or 0.0),
        token_usage=int(float(row.get("token_usage") or 0)),
        langfuse_trace_id=row.get("langfuse_trace_id", ""),
        human_reviewed=row.get("human_reviewed", "").lower() == "true",
        human_override=row.get("human_override", "").lower() == "true",
        errors=_json_list(row.get("errors", "")),
    )


def _json_list(value: str) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: str) -> dict[str, list[str]]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def save_summary(summary: dict[str, Any], output_dir: Path = DEFAULT_RESULTS_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_claim_level_csv(
    results: list[ExperimentResult], output_dir: Path = DEFAULT_RESULTS_DIR
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "claim_level_results.csv"
    fields = [
        "claim_id",
        "mode",
        "final_decision",
        "routing_path",
        "called_tools_by_agent",
        "latency_ms",
        "token_usage",
        "langfuse_trace_id",
        "human_reviewed",
        "human_override",
        "errors",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = result.to_dict()
            row["routing_path"] = json.dumps(row["routing_path"], ensure_ascii=False)
            row["called_tools_by_agent"] = json.dumps(
                row["called_tools_by_agent"], ensure_ascii=False
            )
            row["errors"] = json.dumps(row["errors"], ensure_ascii=False)
            writer.writerow({field: row.get(field, "") for field in fields})


def write_agent_suggestions(
    results_path: Path,
    output_path: Path = DEFAULT_SUGGESTIONS,
    mode: str = "multi_agent",
    suggestions_dir: Path | None = DEFAULT_SUGGESTIONS_DIR,
) -> list[dict[str, Any]]:
    """Create reviewer-facing label suggestions from saved experiment results."""
    suggestions = []
    for result in load_results(results_path):
        if result.mode != mode:
            continue
        suggestion = _suggestion_from_result(result)
        suggestions.append(suggestion)
        if suggestions_dir:
            _write_json(suggestions_dir / f"{result.claim_id}.json", suggestion)

    _write_json(output_path, {"suggestions": suggestions})
    return suggestions


def _suggestion_from_result(result: ExperimentResult) -> dict[str, Any]:
    return {
        "claim_id": result.claim_id,
        "source_mode": result.mode,
        "final_decision": normalize_final_decision(result.final_decision),
        "missing_docs": _extract_issue_codes(result, "missing_docs"),
        "icd_codes": _extract_list(result, "icd_codes"),
        "exclusions": _extract_list(result, "exclusions"),
        "quality_issues": _extract_issue_codes(result, "quality_issues"),
        "routing_path": result.routing_path,
        "called_tools_by_agent": result.called_tools_by_agent,
        "agent_outputs": result.agent_outputs,
        "langfuse_trace_id": result.langfuse_trace_id,
        "errors": result.errors,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize(
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH,
    multi_results_path: Path | None = None,
    single_results_path: Path | None = None,
    output_dir: Path = DEFAULT_RESULTS_DIR,
    labels_path: Path | None = None,
) -> dict[str, Any]:
    dataset = load_ground_truth(ground_truth_path)
    claims = dataset.get("claims", [])
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    labels_by_id = claims_by_id
    label_source = ground_truth_path
    if labels_path:
        reviewed_labels = load_reviewed_labels(labels_path)
        if reviewed_labels:
            labels_by_id = {**claims_by_id, **reviewed_labels}
            label_source = labels_path

    results: list[ExperimentResult] = []
    if multi_results_path:
        results.extend(load_results(multi_results_path))
    if single_results_path:
        results.extend(load_results(single_results_path))

    labelled_claim_ids = {
        claim_id
        for claim_id, claim in labels_by_id.items()
        if normalize_final_decision(claim.get("expected_decision"))
        in {"accept", "reject", "needs_review"}
        and claim.get("label_status", "final") in {"reviewed", "final"}
    }
    summary: dict[str, Any] = {
        "dataset": dataset.get("metadata", {}),
        "label_source": str(label_source),
        "labelled_claim_count": len(labelled_claim_ids),
        "result_count": len(results),
        "by_mode": {},
        "notes": [],
    }

    if not labelled_claim_ids:
        summary["notes"].append(
            "No finalized manual labels found; accuracy metrics are not computed."
        )

    for mode in ["multi_agent", "single_agent"]:
        mode_results = [result for result in results if result.mode == mode]
        comparable = [result for result in mode_results if result.claim_id in labelled_claim_ids]
        y_true = [
            normalize_final_decision(labels_by_id[result.claim_id].get("expected_decision"))
            for result in comparable
        ]
        y_pred = [normalize_final_decision(result.final_decision) for result in comparable]

        mode_summary: dict[str, Any] = {
            "result_count": len(mode_results),
            "comparable_count": len(comparable),
            "performance": compute_latency_percentiles([r.latency_ms for r in mode_results]),
            "token_usage": {
                "total_tokens": sum(r.token_usage for r in mode_results),
                "avg_tokens_per_claim": (
                    sum(r.token_usage for r in mode_results) / len(mode_results)
                    if mode_results
                    else 0.0
                ),
            },
            "human_review_rate": compute_human_review_rate(
                len(mode_results), sum(1 for r in mode_results if r.human_reviewed)
            ),
            "trace_completeness": compute_trace_completeness([r.to_dict() for r in mode_results]),
        }

        if comparable:
            mode_summary["decision"] = compute_f1_scores(y_true, y_pred)
            mode_summary["completeness"] = compute_completeness_accuracy(
                [labels_by_id[r.claim_id].get("expected_missing_docs", []) for r in comparable],
                [_extract_issue_codes(r, "missing_docs") for r in comparable],
            )
            mode_summary["quality_issues"] = compute_set_f1(
                [labels_by_id[r.claim_id].get("expected_quality_issues", []) for r in comparable],
                [_extract_issue_codes(r, "quality_issues") for r in comparable],
            )
            mode_summary["icd_detection"] = compute_set_f1(
                [labels_by_id[r.claim_id].get("expected_icd_codes", []) for r in comparable],
                [_extract_list(r, "icd_codes") for r in comparable],
            )
            mode_summary["exclusion_detection"] = compute_set_f1(
                [labels_by_id[r.claim_id].get("expected_exclusions", []) for r in comparable],
                [_extract_list(r, "exclusions") for r in comparable],
            )
            mode_summary["routing_accuracy"] = compute_path_accuracy(
                [labels_by_id[r.claim_id].get("expected_routing_path", []) for r in comparable],
                [r.routing_path for r in comparable],
            )
            expected_tools, called_tools = _tool_vectors(comparable, labels_by_id)
            mode_summary["tool_usage"] = compute_tool_f1(expected_tools, called_tools)
            mode_summary["invalid_tool_call_rate"] = compute_invalid_tool_call_rate(
                expected_tools, called_tools
            )
            mode_summary["tool_failure_rate"] = compute_tool_failure_rate(
                [tool for r in comparable for tool in r.tool_results]
            )
        summary["by_mode"][mode] = mode_summary

    save_summary(summary, output_dir)
    save_claim_level_csv(results, output_dir)
    DEFAULT_REPORT_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    return summary


def _extract_issue_codes(result: ExperimentResult, key: str) -> list[str]:
    single = result.agent_outputs.get("single_agent", {})
    if key in single and isinstance(single[key], list):
        return [str(item) for item in single[key]]

    codes: list[str] = []
    for output in result.agent_outputs.values():
        if not isinstance(output, dict):
            continue
        for issue in output.get("issues", []):
            if isinstance(issue, dict) and issue.get("code"):
                codes.append(str(issue["code"]))
    return sorted(set(codes))


def _extract_list(result: ExperimentResult, key: str) -> list[str]:
    single = result.agent_outputs.get("single_agent", {})
    if key in single and isinstance(single[key], list):
        return [str(item) for item in single[key]]

    values: list[str] = []
    for output in result.agent_outputs.values():
        if not isinstance(output, dict):
            continue
        evidence = output.get("evidence") or {}
        if isinstance(evidence, dict) and isinstance(evidence.get(key), list):
            values.extend(str(item) for item in evidence[key])
    return sorted(set(values))


def _tool_vectors(
    results: list[ExperimentResult],
    claims_by_id: dict[str, dict[str, Any]],
) -> tuple[list[list[str]], list[list[str]]]:
    expected: list[list[str]] = []
    called: list[list[str]] = []
    for result in results:
        expected_by_agent = get_expected_tools(claims_by_id[result.claim_id])
        expected.append([tool for tools in expected_by_agent.values() for tool in tools])
        called.append([tool for tools in result.called_tools_by_agent.values() for tool in tools])
    return expected, called


def main() -> None:
    parser = argparse.ArgumentParser(description="Run thesis evaluation utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    metrics = subparsers.add_parser("summarize", help="Summarize saved experiment results.")
    metrics.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    metrics.add_argument("--labels", type=Path)
    metrics.add_argument("--multi-results", type=Path)
    metrics.add_argument("--single-results", type=Path)
    metrics.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)

    suggestions = subparsers.add_parser(
        "build-suggestions",
        help="Build agent-assisted labeling suggestions from saved results.",
    )
    suggestions.add_argument("--results", type=Path, required=True)
    suggestions.add_argument("--output", type=Path, default=DEFAULT_SUGGESTIONS)
    suggestions.add_argument("--mode", default="multi_agent")

    args = parser.parse_args()
    if args.command == "summarize":
        summary = summarize(
            args.ground_truth,
            args.multi_results,
            args.single_results,
            args.output_dir,
            args.labels,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "build-suggestions":
        rows = write_agent_suggestions(args.results, args.output, args.mode)
        print(f"Wrote {len(rows)} suggestions: {args.output}")


if __name__ == "__main__":
    main()
