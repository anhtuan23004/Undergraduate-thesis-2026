"""LLM-assisted reference label drafting."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from eval.baseline import GeminiBaselineAdapter
from eval.claim_context import build_claim_context
from eval.document_text import extract_pdf_text
from eval.json_utils import write_json_file
from eval.paths import (
    AUDIT_QUEUE,
    CLAIM_RESULTS_DIR,
    GROUND_TRUTH,
    OCR_CACHE_DIR,
    REVIEWED_LABELS,
    SINGLE_AGENT_RESULTS_DIR,
)
from eval.runner import load_ground_truth

REFERENCE_LABEL_MODEL = "gemini-3.1-pro-preview"
DEFAULT_PDF_MAX_CHARS = 20000


class ReferenceLabelAdapter(Protocol):
    def invoke(self, prompt: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
        """Return parsed label output, raw text, and metadata."""


def run_label_reference(
    args: argparse.Namespace,
    adapter: ReferenceLabelAdapter | None = None,
) -> dict[str, Any]:
    """Draft reference labels without using agent predictions as labels."""
    dataset = load_ground_truth(args.ground_truth)
    claims = list(dataset.get("claims", []))
    if args.claim_id:
        wanted = set(args.claim_id)
        claims = [claim for claim in claims if claim.get("claim_id") in wanted]
    if args.limit is not None:
        claims = claims[: args.limit]

    if args.dry_run:
        for index, claim in enumerate(claims, start=1):
            print(f"[{index}/{len(claims)}] label-reference {claim.get('claim_id')}")
        return {"metadata": _metadata(args.model, 0, _label_source(args)), "labels": []}

    llm = adapter or GeminiBaselineAdapter(args.model, use_tools=False)
    labels = _load_existing_labels(args.output) if args.skip_existing else []
    labels_by_id = {str(label.get("claim_id", "")): label for label in labels}
    label_source = _label_source(args)
    for index, claim in enumerate(claims, start=1):
        claim_id = str(claim.get("claim_id", ""))
        if args.skip_existing and claim_id in labels_by_id:
            print(f"[{index}/{len(claims)}] skip existing reference label {claim_id}", flush=True)
            continue
        print(f"[{index}/{len(claims)}] label-reference {claim_id}", flush=True)
        prompt = build_reference_label_prompt(
            claim,
            args.ocr_cache_dir,
            include_agent_results=getattr(args, "include_agent_results", False),
            multi_results_dir=getattr(args, "multi_results", CLAIM_RESULTS_DIR),
            single_results_dir=getattr(args, "single_results", SINGLE_AGENT_RESULTS_DIR),
            pdf_max_chars=getattr(args, "pdf_max_chars", DEFAULT_PDF_MAX_CHARS),
        )
        parsed, _raw_text, _metadata_payload = llm.invoke(prompt)
        label = _label_from_model_output(claim, parsed, args.model, label_source)
        labels_by_id[label["claim_id"]] = label
        labels = [labels_by_id[key] for key in sorted(labels_by_id)]
        _write_outputs(args.output, args.audit_queue, args.model, labels, label_source)

    payload = _payload(args.model, labels, label_source)
    _write_outputs(args.output, args.audit_queue, args.model, labels, label_source)
    return payload


def build_reference_label_prompt(
    claim: dict[str, Any],
    ocr_cache_dir: Path,
    *,
    include_agent_results: bool = False,
    multi_results_dir: Path = CLAIM_RESULTS_DIR,
    single_results_dir: Path = SINGLE_AGENT_RESULTS_DIR,
    pdf_max_chars: int = DEFAULT_PDF_MAX_CHARS,
) -> str:
    """Build the label prompt from manifest, evidence, and optional agent results."""
    evidence = _load_ocr_evidence(claim, ocr_cache_dir)
    pdf_evidence = _load_pdf_evidence(claim, pdf_max_chars)
    agent_results = (
        _load_agent_result_evidence(claim, multi_results_dir, single_results_dir)
        if include_agent_results
        else {}
    )
    policy = (
        "Bạn được xem output của multi-agent và single-agent như ý kiến tham khảo. "
        "Không copy máy móc final_decision; nếu output agent mâu thuẫn với PDF/OCR evidence "
        "thì ưu tiên bằng chứng trong tài liệu. Ghi rõ disagreement trong expert_notes."
        if include_agent_results
        else "Không dùng kết quả agent hoặc final_decision của hệ thống làm nhãn. "
        "Chỉ dựa trên metadata hồ sơ, OCR/cache evidence, PDF text, và quy tắc nghiệp vụ trong đề bài."
    )
    return f"""Bạn là reviewer tạo nhãn tham chiếu cho đánh giá thesis.

{policy}

Trả về DUY NHẤT một JSON object hợp lệ:
{{
  "expected_decision": "accept | reject | needs_review",
  "expected_missing_docs": ["..."],
  "expected_icd_codes": ["..."],
  "expected_medications": ["..."],
  "expected_exclusions": ["..."],
  "expected_quality_issues": ["..."],
  "expected_consistency_issues": ["..."],
  "expected_routing_path": ["..."],
  "expected_tools_by_agent": {{"CompletenessAgent": ["..."], "QualityAgent": ["..."]}},
  "complexity": "simple | ambiguous | complex",
  "confidence": 0.0,
  "expert_notes": "..."
}}

Claim metadata:
{json.dumps(_claim_context(claim), ensure_ascii=False, indent=2)}

OCR/cache evidence:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

PDF text evidence:
{json.dumps(pdf_evidence, ensure_ascii=False, indent=2)}

Agent result evidence:
{json.dumps(agent_results, ensure_ascii=False, indent=2)}
"""


def build_parser(add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft LLM-assisted reference labels.",
        add_help=add_help,
    )
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    parser.add_argument("--output", type=Path, default=REVIEWED_LABELS)
    parser.add_argument("--audit-queue", type=Path, default=AUDIT_QUEUE)
    parser.add_argument("--ocr-cache-dir", type=Path, default=OCR_CACHE_DIR)
    parser.add_argument("--multi-results", type=Path, default=CLAIM_RESULTS_DIR)
    parser.add_argument("--single-results", type=Path, default=SINGLE_AGENT_RESULTS_DIR)
    parser.add_argument("--include-agent-results", action="store_true")
    parser.add_argument("--pdf-max-chars", type=int, default=DEFAULT_PDF_MAX_CHARS)
    parser.add_argument("--model", default=REFERENCE_LABEL_MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--claim-id", action="append")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _label_from_model_output(
    claim: dict[str, Any],
    output: dict[str, Any],
    model: str,
    label_source: str = "llm_assisted_audited",
) -> dict[str, Any]:
    return {
        "claim_id": str(claim.get("claim_id", "")),
        "file_name": claim.get("file_name", ""),
        "file_path": claim.get("file_path", ""),
        "category_code": claim.get("category_code", ""),
        "expected_decision": str(output.get("expected_decision", "")),
        "expected_missing_docs": _string_list(output.get("expected_missing_docs", [])),
        "expected_icd_codes": _string_list(output.get("expected_icd_codes", [])),
        "expected_medications": _string_list(output.get("expected_medications", [])),
        "expected_exclusions": _string_list(output.get("expected_exclusions", [])),
        "expected_quality_issues": _string_list(output.get("expected_quality_issues", [])),
        "expected_consistency_issues": _string_list(output.get("expected_consistency_issues", [])),
        "expected_routing_path": _string_list(output.get("expected_routing_path", [])),
        "expected_tools_by_agent": output.get("expected_tools_by_agent", {}),
        "complexity": str(output.get("complexity", "simple")),
        "label_status": "reviewed",
        "label_source": label_source,
        "llm_model": model,
        "reviewer": (
            "gemini_judge" if label_source == "llm_judge_with_agent_outputs" else "gemini_draft"
        ),
        "confidence": float(output.get("confidence") or 0.0),
        "expert_notes": str(output.get("expert_notes", "")),
    }


def _audit_rows_for_label(label: dict[str, Any]) -> list[dict[str, str]]:
    reasons = []
    if float(label.get("confidence") or 0.0) < 0.75:
        reasons.append("low_confidence")
    if label.get("expected_decision") == "needs_review":
        reasons.append("needs_review_label")
    if not label.get("expert_notes"):
        reasons.append("missing_evidence_notes")
    if not reasons:
        return []
    return [
        {
            "claim_id": str(label.get("claim_id", "")),
            "reason": ";".join(reasons),
            "priority": "high" if "low_confidence" in reasons else "medium",
            "current_label_status": str(label.get("label_status", "")),
            "suggested_action": "manual_audit",
        }
    ]


def _metadata(model: str, label_count: int, label_source: str) -> dict[str, Any]:
    return {
        "labeling_method": label_source,
        "llm_model": model,
        "created_at": datetime.now(UTC).isoformat(),
        "audit_policy": (
            "LLM judge uses document evidence plus agent outputs; audit low-confidence, "
            "needs_review, disagreement, missing-evidence, and sampled labels."
        ),
        "reviewed_count": label_count,
        "final_count": 0,
    }


def _payload(model: str, labels: list[dict[str, Any]], label_source: str) -> dict[str, Any]:
    return {"metadata": _metadata(model, len(labels), label_source), "labels": labels}


def _write_outputs(
    output_path: Path,
    audit_queue_path: Path,
    model: str,
    labels: list[dict[str, Any]],
    label_source: str,
) -> None:
    _write_json(output_path, _payload(model, labels, label_source))
    audit_rows = [row for label in labels for row in _audit_rows_for_label(label)]
    _write_audit_queue(audit_queue_path, audit_rows)


def _load_existing_labels(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("labels", [])
    return [row for row in rows if isinstance(row, dict) and row.get("claim_id")]


def _load_ocr_evidence(claim: dict[str, Any], ocr_cache_dir: Path) -> dict[str, Any]:
    claim_id = str(claim.get("claim_id", ""))
    cache_path = ocr_cache_dir / f"{claim_id}.json"
    if cache_path.exists():
        return {
            "source": str(cache_path),
            "payload": json.loads(cache_path.read_text(encoding="utf-8")),
        }
    return {
        "source": "manifest_only",
        "warning": "No OCR cache snapshot found. PDF text fallback is used.",
        "file_path": claim.get("file_path", ""),
        "pdf_text": _extract_pdf_text(claim.get("file_path", "")),
    }


def _load_pdf_evidence(claim: dict[str, Any], max_chars: int) -> dict[str, Any]:
    file_path = claim.get("file_path", "")
    return {
        "file_path": file_path,
        "pdf_text": _extract_pdf_text(file_path, max_chars=max_chars),
        "max_chars": max_chars,
    }


def _load_agent_result_evidence(
    claim: dict[str, Any],
    multi_results_dir: Path,
    single_results_dir: Path,
) -> dict[str, Any]:
    claim_id = str(claim.get("claim_id", ""))
    return {
        "multi_agent": _load_result_summary(multi_results_dir / f"{claim_id}.json"),
        "single_agent": _load_result_summary(single_results_dir / f"{claim_id}.json"),
    }


def _load_result_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": "found",
        "path": str(path),
        "mode": payload.get("mode", ""),
        "final_decision": payload.get("final_decision", ""),
        "agent_outputs": payload.get("agent_outputs", {}),
        "routing_path": payload.get("routing_path", []),
        "called_tools_by_agent": payload.get("called_tools_by_agent", {}),
        "errors": payload.get("errors", []),
    }


def _claim_context(claim: dict[str, Any]) -> dict[str, Any]:
    return build_claim_context(claim)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_json_file(path, payload)


def _write_audit_queue(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["claim_id", "reason", "priority", "current_label_status", "suggested_action"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _label_source(args: argparse.Namespace) -> str:
    return (
        "llm_judge_with_agent_outputs"
        if getattr(args, "include_agent_results", False)
        else "llm_assisted_audited"
    )


def _extract_pdf_text(file_path: Any, max_chars: int = 20000) -> str:
    return extract_pdf_text(file_path, max_chars=max_chars)
