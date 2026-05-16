"""Batch-run claim workflows for Chapter 4 experiment data collection.

The CLI reads the reviewed dataset manifest, calls the existing agent-service
workflow API, and stores normalized experiment rows incrementally. It is meant
to produce agent suggestions for manual ground-truth review, not to mutate the
ground-truth file directly.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from eval.paths import (
    AGENT_SUGGESTIONS,
    CLAIM_RESULTS_DIR,
    CLAIM_SUGGESTIONS_DIR,
    GROUND_TRUTH,
    HISTORY,
    ROOT,
)
from eval.runner import write_agent_suggestions
from eval.schemas import ExperimentResult, normalize_final_decision

DEFAULT_BASE_URL = "http://localhost:8003/api/v1"
DEFAULT_RESULTS_DIR = CLAIM_RESULTS_DIR
DEFAULT_SUGGESTIONS = AGENT_SUGGESTIONS
DEFAULT_SUGGESTIONS_DIR = CLAIM_SUGGESTIONS_DIR
DEFAULT_HISTORY = HISTORY

NODE_BY_STEP = {
    "completeness_agent": "completeness_check",
    "quality_agent": "quality_check",
    "decision_agent": "final_decision",
    "agent_review": "agent_review",
    "human_review": "human_review",
}


def load_claims(ground_truth_path: Path) -> list[dict[str, Any]]:
    """Load claim rows from the dataset manifest."""
    payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    return list(payload.get("claims", []))


def result_path(results_dir: Path, claim_id: str) -> Path:
    """Return the per-claim result path."""
    return results_dir / f"{claim_id}.json"


def load_saved_results(results_dir: Path) -> list[ExperimentResult]:
    """Load saved per-claim result files."""
    if not results_dir.exists():
        return []
    return [
        ExperimentResult(**json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(results_dir.glob("*.json"))
    ]


def save_result(results_dir: Path, result: ExperimentResult) -> Path:
    """Persist one normalized result row as one claim JSON file."""
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_path(results_dir, result.claim_id)
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def load_history(history_path: Path) -> dict[str, Any]:
    """Load claim processing history manifest."""
    if not history_path.exists():
        return {"claims": {}}
    return json.loads(history_path.read_text(encoding="utf-8"))


def save_history(history_path: Path, history: dict[str, Any]) -> None:
    """Persist claim processing history manifest."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    claims = history.get("claims", {})
    counts = _status_counts(claims)
    history["summary"] = {
        "total": sum(counts.values()),
        **counts,
        "updated_at": _now_iso(),
    }
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def update_history(
    history: dict[str, Any],
    claim: dict[str, Any],
    state: str,
    **fields: Any,
) -> None:
    """Update one claim entry in the run history manifest."""
    claim_id = str(claim.get("claim_id", ""))
    claims = history.setdefault("claims", {})
    previous = claims.get(claim_id, {})
    entry = {
        **previous,
        "claim_id": claim_id,
        "file_name": claim.get("file_name", ""),
        "file_path": _display_path(claim.get("file_path", "")),
        "category_code": claim.get("category_code", ""),
        "status": state,
        "updated_at": _now_iso(),
        **fields,
    }
    if state == "completed" and "error" not in fields:
        entry.pop("error", None)
    if state == "running":
        entry["started_at"] = entry["updated_at"]
    if state in {"completed", "failed", "skipped"}:
        entry["finished_at"] = entry["updated_at"]
    claims[claim_id] = entry


def initialize_history(history: dict[str, Any], claims: list[dict[str, Any]]) -> None:
    """Ensure all selected claims exist in the history manifest."""
    for claim in claims:
        claim_id = str(claim.get("claim_id", ""))
        if claim_id not in history.get("claims", {}):
            update_history(history, claim, "pending")


def upload_document(base_url: str, file_path: Path, timeout: float) -> dict[str, Any]:
    """Upload a host-side PDF and return the server-side path/hash."""
    with file_path.open("rb") as handle:
        response = requests.post(
            f"{base_url.rstrip('/')}/workflows/upload",
            files={"file": (file_path.name, handle, "application/pdf")},
            timeout=timeout,
        )
    _raise_for_status(response, "upload document")
    return response.json()


def run_claim(
    claim: dict[str, Any],
    base_url: str,
    upload: bool,
    timeout: float,
) -> ExperimentResult:
    """Run one claim through the multi-agent workflow API."""
    claim_id = str(claim.get("claim_id", ""))
    local_file = ROOT / claim["file_path"]
    if local_file.exists():
        input_file = str(local_file)
    else:
        input_file = str(claim["file_path"])

    file_hash = claim.get("file_hash")
    if upload:
        uploaded = upload_document(base_url, Path(input_file), timeout)
        input_file = str(uploaded["file_path"])
        file_hash = uploaded.get("file_hash")

    payload = {
        "claim_id": claim_id,
        "policy_number": str(claim.get("policy_number") or claim.get("policy_id") or ""),
        "input_file": input_file,
        "file_hash": file_hash,
    }

    started = time.perf_counter()
    response = requests.post(
        f"{base_url.rstrip('/')}/workflows/run",
        json=payload,
        timeout=timeout,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    _raise_for_status(response, "run workflow")
    return workflow_response_to_result(response.json(), latency_ms)


def _raise_for_status(response: requests.Response, action: str) -> None:
    """Raise an HTTPError that includes FastAPI's structured error body."""
    if response.ok:
        return

    detail = _response_error_detail(response)
    message = (
        f"{response.status_code} {response.reason} while attempting to {action}: {response.url}"
    )
    if detail:
        message = f"{message} - {detail}"
    raise requests.HTTPError(message, response=response)


def _response_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    detail = payload.get("detail") if isinstance(payload, dict) else payload
    if isinstance(detail, dict):
        parts = [str(detail.get(key)) for key in ("error", "error_detail") if detail.get(key)]
        return " | ".join(parts)
    if detail:
        return str(detail)
    return response.text.strip()


def workflow_response_to_result(data: dict[str, Any], latency_ms: float) -> ExperimentResult:
    """Normalize a workflow API response into the shared experiment schema."""
    history = data.get("history") or []
    final_result = data.get("final_result") or {}
    final_decision = normalize_final_decision(final_result.get("decision"))
    if not final_decision and data.get("pending_human_review"):
        final_decision = "needs_review"

    errors: list[str] = []
    if data.get("error"):
        errors.append(str(data["error"]))

    return ExperimentResult(
        claim_id=str(data.get("claim_id", "")),
        mode="multi_agent",
        agent_outputs=_agent_outputs(data),
        final_decision=final_decision,
        routing_path=extract_routing_path(history, data.get("current_step"), data.get("pause_at")),
        called_tools_by_agent=extract_called_tools(history),
        **extract_token_usage(history),
        latency_ms=latency_ms,
        langfuse_trace_id=str(data.get("langfuse_trace_id") or ""),
        human_reviewed=bool(data.get("pending_human_review") or data.get("paused")),
        errors=errors,
    )


def extract_routing_path(
    history: list[dict[str, Any]],
    current_step: str | None,
    pause_at: str | None,
) -> list[str]:
    """Build a compact LangGraph route from local workflow history."""
    path: list[str] = []
    for entry in history:
        step = str(entry.get("step") or "")
        node = NODE_BY_STEP.get(step, step)
        if node and node not in path:
            path.append(node)

    for step in [current_step, pause_at]:
        node = _normalize_current_step(step)
        if node and node not in path:
            path.append(node)
    return path


def extract_called_tools(history: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Extract tool names if workflow history contains tool-call metadata."""
    called: dict[str, list[str]] = {}
    for entry in history:
        agent = entry.get("agent") or entry.get("agent_name") or entry.get("step") or "unknown"
        tools = entry.get("called_tools") or entry.get("tools") or []
        if isinstance(tools, str):
            tools = [tools]
        called.setdefault(str(agent), [])
        called[str(agent)].extend(str(tool) for tool in tools)
    return {agent: sorted(set(tools)) for agent, tools in called.items()}


def extract_token_usage(history: list[dict[str, Any]]) -> dict[str, int | str]:
    """Sum provider token usage emitted by workflow history entries."""
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    observed = False
    for entry in history:
        usage = entry.get("token_usage")
        if not isinstance(usage, dict):
            continue
        if usage.get("token_usage_source") != "provider_metadata":
            continue
        observed = True
        prompt_tokens += int(usage.get("prompt_tokens") or 0)
        completion_tokens += int(usage.get("completion_tokens") or 0)
        total_tokens += int(usage.get("token_usage") or 0)

    if not observed:
        return {}
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "token_usage": total_tokens,
        "token_usage_source": "provider_metadata",
    }


def _agent_outputs(data: dict[str, Any]) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    if data.get("agent_1_result") is not None:
        outputs["CompletenessAgent"] = data["agent_1_result"]
    if data.get("agent_2_result") is not None:
        outputs["QualityAgent"] = data["agent_2_result"]
    if data.get("final_result") is not None:
        outputs["DecisionAgent"] = data["final_result"]
    return outputs


def _normalize_current_step(step: str | None) -> str:
    if not step:
        return ""
    value = step.removeprefix("completed_")
    return NODE_BY_STEP.get(value, value)


def run_batch(args: argparse.Namespace) -> list[ExperimentResult]:
    """Execute selected claims and write results incrementally."""
    claims = load_claims(args.ground_truth)
    if args.claim_id:
        wanted = set(args.claim_id)
        claims = [claim for claim in claims if claim.get("claim_id") in wanted]
    if args.limit is not None:
        claims = claims[: args.limit]

    if args.dry_run:
        for index, claim in enumerate(claims, start=1):
            print(f"[{index}/{len(claims)}] {claim.get('claim_id')}: {claim.get('file_path')}")
        return []

    history = load_history(args.history)
    initialize_history(history, claims)
    save_history(args.history, history)

    if getattr(args, "deprecated_no_upload", False):
        print(
            "Warning: --no-upload is deprecated; current agent-service requires "
            "workflow inputs to be under UPLOADS_DIR, so eval will upload documents."
        )

    results = load_saved_results(args.results_dir) if args.skip_existing else []
    existing_ids = {result.claim_id for result in results}

    for index, claim in enumerate(claims, start=1):
        result = _run_one_claim(index, len(claims), claim, args, history, existing_ids)
        if result is None:
            continue

        claim_id = str(claim.get("claim_id", ""))
        results = [row for row in results if row.claim_id != claim_id]
        results.append(result)
        output_file = save_result(args.results_dir, result)
        _update_history_from_result(history, claim, result, output_file)
        save_history(args.history, history)

    if args.build_suggestions:
        suggestions = write_agent_suggestions(
            args.results_dir,
            args.suggestions,
            suggestions_dir=args.suggestions_dir,
        )
        _attach_suggestions_to_history(args.history, args.suggestions_dir, suggestions)
        print(f"Wrote {len(suggestions)} suggestions: {args.suggestions}")

    return results


def _run_one_claim(
    index: int,
    total: int,
    claim: dict[str, Any],
    args: argparse.Namespace,
    history: dict[str, Any],
    existing_ids: set[str],
) -> ExperimentResult | None:
    claim_id = str(claim.get("claim_id", ""))
    if args.skip_existing and claim_id in existing_ids:
        print(f"[{index}/{total}] skip existing {claim_id}")
        _mark_existing_result_skipped(history, claim, result_path(args.results_dir, claim_id))
        save_history(args.history, history)
        return None

    try:
        print(f"[{index}/{total}] run {claim_id}: {claim.get('file_name', '')}")
        update_history(history, claim, "running")
        save_history(args.history, history)
        return run_claim(claim, args.base_url, args.upload, args.timeout)
    except Exception as exc:
        update_history(history, claim, "failed", error=str(exc))
        save_history(args.history, history)
        if args.fail_fast:
            raise
        print(f"[{index}/{total}] error {claim_id}: {exc}")
        return ExperimentResult(claim_id=claim_id, mode="multi_agent", errors=[str(exc)])


def _update_history_from_result(
    history: dict[str, Any],
    claim: dict[str, Any],
    result: ExperimentResult,
    output_file: Path,
) -> None:
    if result.errors:
        update_history(
            history,
            claim,
            "failed",
            error="; ".join(result.errors),
            output_file=_display_path(output_file),
        )
        return
    update_history(
        history,
        claim,
        "completed",
        final_decision=result.final_decision,
        latency_ms=result.latency_ms,
        output_file=_display_path(output_file),
    )


def _mark_existing_result_skipped(
    history: dict[str, Any],
    claim: dict[str, Any],
    output_file: Path,
) -> None:
    claim_id = str(claim.get("claim_id", ""))
    previous = history.get("claims", {}).get(claim_id, {})
    state = previous.get("status", "skipped")
    if previous.get("final_decision") and not previous.get("error"):
        state = "completed"
    elif previous.get("error"):
        state = "failed"
    elif state not in {"completed", "failed"}:
        state = "skipped"
    update_history(
        history,
        claim,
        state,
        last_action="skipped_existing",
        output_file=_display_path(output_file),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run dataset claims through the existing multi-agent workflow API."
    )
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--suggestions", type=Path, default=DEFAULT_SUGGESTIONS)
    parser.add_argument("--suggestions-dir", type=Path, default=DEFAULT_SUGGESTIONS_DIR)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--claim-id", action="append", help="Run only one claim id; repeatable.")
    parser.add_argument(
        "--no-upload",
        dest="deprecated_no_upload",
        action="store_true",
        help=(
            "Deprecated no-op. Current agent-service requires workflow inputs under "
            "UPLOADS_DIR, so eval uploads documents before running workflows."
        ),
    )
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--build-suggestions", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="List selected claims without calling APIs."
    )
    parser.set_defaults(upload=True, deprecated_no_upload=False)
    return parser


def _status_counts(claims: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(["pending", "running", "completed", "failed", "skipped"], 0)
    for entry in claims.values():
        state = str(entry.get("status", "pending"))
        counts[state if state in counts else "pending"] += 1
    return counts


def _attach_suggestions_to_history(
    history_path: Path,
    suggestions_dir: Path,
    suggestions: list[dict[str, Any]],
) -> None:
    history = load_history(history_path)
    for suggestion in suggestions:
        claim_id = str(suggestion.get("claim_id", ""))
        if claim_id in history.get("claims", {}):
            history["claims"][claim_id]["suggestion_file"] = _display_path(
                suggestions_dir / f"{claim_id}.json"
            )
            history["claims"][claim_id]["updated_at"] = _now_iso()
    save_history(history_path, history)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _display_path(path: str | Path) -> str:
    if not path:
        return ""
    candidate = Path(path)
    try:
        return str(candidate.relative_to(ROOT))
    except ValueError:
        return str(candidate)


def main() -> None:
    args = build_parser().parse_args()
    results = run_batch(args)
    if not args.dry_run:
        print(f"Wrote {len(results)} results: {args.results_dir}")


if __name__ == "__main__":
    main()
