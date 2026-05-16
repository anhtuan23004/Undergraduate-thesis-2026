"""Single-agent baseline runner for RQ5."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from eval.claim_context import build_claim_context
from eval.document_text import extract_pdf_text
from eval.paths import GROUND_TRUTH, OCR_CACHE_DIR, ROOT, SINGLE_AGENT_RESULTS_DIR
from eval.runner import load_ground_truth, load_results
from eval.schemas import ExperimentResult, normalize_final_decision
from eval.token_usage import token_usage_from_metadata

DEFAULT_BASELINE_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MONGODB_URL = (
    "mongodb://admin:admin123@localhost:27017/claims?authSource=admin&directConnection=true"
)
DEFAULT_MONGODB_DB = "claims"
PREFERRED_OCR_STAGES = ("phase2_extracted", "v1_document", "phase1_classified")


class BaselineAdapter(Protocol):
    """Boundary for single-agent LLM calls."""

    def invoke(self, prompt: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
        """Return parsed output, raw text, and response metadata."""


class GeminiBaselineAdapter:
    """Gemini-backed baseline adapter, loaded only when used."""

    def __init__(self, model_name: str, *, use_tools: bool = True) -> None:
        self.model_name = model_name
        self.use_tools = use_tools

    def invoke(self, prompt: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required to run the single-agent baseline.")

        if self.use_tools:
            return self._invoke_with_tools(prompt, api_key)
        return self._invoke_plain(prompt, api_key)

    def _invoke_plain(
        self, prompt: str, api_key: str
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0,
            max_output_tokens=4096,
        )
        response = llm.invoke(prompt)
        raw_text = _response_text(response)
        return _parse_json_object(raw_text), raw_text, getattr(response, "response_metadata", {})

    def _invoke_with_tools(
        self,
        prompt: str,
        api_key: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        from langchain.agents import create_agent
        from langchain_google_genai import ChatGoogleGenerativeAI

        tools, skill_contexts = _load_single_agent_tools()
        llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0,
            max_output_tokens=4096,
        )
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=_single_agent_system_prompt(skill_contexts),
        )
        result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        raw_text = _extract_agent_text(result)
        metadata = {
            "called_tools": _extract_called_tools(result),
            "tool_calling": True,
            **_extract_token_usage_metadata(result),
        }
        return _parse_json_object(raw_text), raw_text, metadata


def run_baseline(
    args: argparse.Namespace,
    adapter: BaselineAdapter | None = None,
) -> list[ExperimentResult]:
    """Run claims through a one-call single-agent baseline."""
    dataset = load_ground_truth(args.ground_truth)
    claims = list(dataset.get("claims", []))
    if args.claim_id:
        wanted = set(args.claim_id)
        claims = [claim for claim in claims if claim.get("claim_id") in wanted]
    if args.limit is not None:
        claims = claims[: args.limit]

    if args.dry_run:
        for index, claim in enumerate(claims, start=1):
            print(
                f"[{index}/{len(claims)}] baseline {claim.get('claim_id')}: {claim.get('file_path')}"
            )
        return []

    args.results_dir.mkdir(parents=True, exist_ok=True)
    existing = {result.claim_id: result for result in load_results(args.results_dir)}
    llm = adapter or GeminiBaselineAdapter(args.model, use_tools=getattr(args, "use_tools", True))
    results: list[ExperimentResult] = []
    for index, claim in enumerate(claims, start=1):
        claim_id = str(claim.get("claim_id", ""))
        if args.skip_existing and claim_id in existing:
            print(f"[{index}/{len(claims)}] skip existing baseline {claim_id}")
            results.append(existing[claim_id])
            continue

        print(f"[{index}/{len(claims)}] run baseline {claim_id}", flush=True)
        prompt, ocr_cache_key = build_baseline_prompt(
            claim,
            args.ocr_cache_dir,
            ocr_source=getattr(args, "ocr_source", "auto"),
            mongo_url=getattr(args, "mongo_url", None),
            mongo_db=getattr(args, "mongo_db", None),
            require_ocr_cache=getattr(args, "require_ocr_cache", False),
            allow_pdf_fallback=getattr(args, "allow_pdf_fallback", False),
        )
        started = time.perf_counter()
        parsed, raw_text, metadata = llm.invoke(prompt)
        latency_ms = (time.perf_counter() - started) * 1000
        token_usage = token_usage_from_metadata(metadata, prompt, raw_text)
        result = ExperimentResult(
            claim_id=claim_id,
            mode="single_agent",
            agent_outputs={"single_agent": parsed},
            final_decision=normalize_final_decision(str(parsed.get("final_decision", ""))),
            routing_path=["single_agent"],
            called_tools_by_agent=_called_tools_by_agent(metadata),
            latency_ms=latency_ms,
            model_name=args.model,
            ocr_cache_key=ocr_cache_key,
            **token_usage,
        )
        save_baseline_result(args.results_dir, result)
        results.append(result)
    return results


def build_baseline_prompt(
    claim: dict[str, Any],
    ocr_cache_dir: Path,
    *,
    ocr_source: str = "auto",
    mongo_url: str | None = None,
    mongo_db: str | None = None,
    require_ocr_cache: bool = False,
    allow_pdf_fallback: bool = False,
) -> tuple[str, str]:
    """Build the structured single-agent prompt from claim metadata and OCR cache."""
    claim_id = str(claim.get("claim_id", ""))
    evidence = _load_ocr_evidence(
        claim,
        ocr_cache_dir,
        ocr_source=ocr_source,
        mongo_url=mongo_url,
        mongo_db=mongo_db,
    )
    if evidence.get("ocr_cache_status") == "missing" and require_ocr_cache:
        raise RuntimeError(f"Missing OCR cache for claim {claim_id}")
    if evidence.get("ocr_cache_status") == "missing" and allow_pdf_fallback:
        evidence["pdf_text"] = _extract_pdf_text(claim.get("file_path", ""))
        evidence["ocr_cache_status"] = "pdf_fallback"
    prompt = f"""Bạn là baseline single-agent cho đánh giá thesis.

Nhiệm vụ: dùng cùng dữ liệu OCR đầu vào để đánh giá một hồ sơ bảo hiểm sức khỏe.
Trả về DUY NHẤT một JSON object hợp lệ với schema:
{{
  "final_decision": "accept | reject | needs_review",
  "missing_docs": ["..."],
  "icd_codes": ["..."],
  "medications": ["..."],
  "exclusions": ["..."],
  "quality_issues": ["..."],
  "consistency_issues": ["..."],
  "quality_assessment": {{
    "decision": "accept | reject | accept_with_edit",
    "valid": true,
    "issues": [
      {{
        "severity": "critical | high | medium | low",
        "code": "ICD_MISMATCH | INVALID_ICD | MEDICINE_MISMATCH | EXCLUDED_DIAGNOSIS | CONSISTENCY_ISSUE | ...",
        "description": "...",
        "reason": "..."
      }}
    ],
    "suggested_updates": [
      {{
        "field": "icd_code | medication | exclusion | consistency",
        "current_value": "...",
        "suggested_value": "...",
        "reference_url": "..."
      }}
    ],
    "evidence": {{
      "diagnoses": ["..."],
      "icd_codes": [{{"code": "...", "diagnosis": "..."}}],
      "medications": [{{"name": "...", "quantity": "..."}}, "..."],
      "total_claim_amount": 0,
      "exclusions_found": false
    }},
    "medical_findings": {{
      "status_message": "success | Warning",
      "data": {{
        "summary": {{"total_warnings": 0, "total_success": 0}},
        "warnings": [
          {{
            "type": "icd_missing | icd_mismatch | excluded_diagnosis | medicine_mismatch | consistency_issue",
            "diagnosis_name": "...",
            "suggested_icd": "...",
            "message": "...",
            "reference_url": "..."
          }}
        ],
        "success": [
          {{
            "type": "icd_valid | medicine_valid | coverage_approved",
            "diagnosis_name": "...",
            "icd": "...",
            "message": "...",
            "reference_url": "..."
          }}
        ]
      }}
    }},
    "message": "...",
    "confidence_score": 0.0
  }},
  "rationale": "..."
}}

Yêu cầu quan trọng:
- `icd_codes` và `medications` là danh sách phát hiện để tính metric.
- `quality_assessment.medical_findings` là phần THẨM ĐỊNH y tế chi tiết, tương đương kết quả Quality Agent.
- Với từng ICD/thuốc quan trọng, hãy phân loại rõ là hợp lệ, không khớp, thiếu bằng chứng, hoặc cần loại trừ.
- Không chỉ liệt kê thuốc/ICD; phải nêu cảnh báo và lý do bằng tiếng Việt.

Claim metadata:
{json.dumps(_claim_context(claim), ensure_ascii=False, indent=2)}

OCR/cache evidence:
{json.dumps(evidence, ensure_ascii=False, indent=2)}
"""
    return prompt, str(evidence.get("ocr_cache_key") or claim_id)


def save_baseline_result(results_dir: Path, result: ExperimentResult) -> Path:
    """Persist one baseline result as a per-claim JSON file."""
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / f"{result.claim_id}.json"
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_parser(add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the single-agent baseline.",
        add_help=add_help,
    )
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH)
    parser.add_argument("--results-dir", type=Path, default=SINGLE_AGENT_RESULTS_DIR)
    parser.add_argument("--ocr-cache-dir", type=Path, default=OCR_CACHE_DIR)
    parser.add_argument(
        "--ocr-source",
        choices=["auto", "mongo", "file"],
        default="auto",
        help="OCR evidence source. auto tries Mongo first, then file snapshots.",
    )
    parser.add_argument("--mongo-url", default=os.environ.get("MONGODB_URL", DEFAULT_MONGODB_URL))
    parser.add_argument("--mongo-db", default=os.environ.get("MONGODB_DB", DEFAULT_MONGODB_DB))
    parser.add_argument(
        "--require-ocr-cache",
        action="store_true",
        help="Fail a claim if no Mongo/file OCR cache is found.",
    )
    parser.add_argument(
        "--allow-pdf-fallback",
        action="store_true",
        help="Use PDF text only when OCR cache is missing. Do not use for RQ5 comparability.",
    )
    parser.add_argument(
        "--no-tools",
        dest="use_tools",
        action="store_false",
        help="Disable tool calling and run the old one-shot prompt baseline.",
    )
    parser.set_defaults(use_tools=True)
    parser.add_argument(
        "--model",
        default=os.environ.get("GEMINI_BASELINE_MODEL")
        or os.environ.get("GEMINI_MODEL")
        or DEFAULT_BASELINE_MODEL,
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--claim-id", action="append")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _claim_context(claim: dict[str, Any]) -> dict[str, Any]:
    return build_claim_context(claim, include_policy_number=True)


def _load_single_agent_tools() -> tuple[list[Any], str]:
    """Load the same skill tools used by the workflow agents."""
    _ensure_agent_service_on_path()
    from tools.skill_loader import load_agent_skills

    tools_by_name: dict[str, Any] = {}
    contexts: list[str] = []
    for agent_name in ["completeness_agent", "quality_agent", "decision_agent"]:
        tools, skill_contexts = load_agent_skills(agent_name)
        for tool in tools:
            tool_name = str(getattr(tool, "name", ""))
            if tool_name and tool_name not in tools_by_name:
                tools_by_name[tool_name] = tool
        if skill_contexts:
            contexts.append(f"## {agent_name}\n{skill_contexts}")
    return list(tools_by_name.values()), "\n\n".join(contexts)


def _ensure_agent_service_on_path() -> None:
    agent_service = ROOT / "src" / "agent-service"
    path = str(agent_service)
    if path not in sys.path:
        sys.path.insert(0, path)


def _single_agent_system_prompt(skill_contexts: str) -> str:
    return f"""Bạn là single-agent baseline cho đánh giá thesis.

Bạn xử lý toàn bộ hồ sơ trong một agent duy nhất, nhưng BẮT BUỘC dùng các tool
phù hợp trước khi kết luận:
- Completeness: classify-benefit, check-required-docs, validate-consistency.
- Quality: check-icd, check-exclusion, search-medicine, validate-medication.
- Decision: aggregate-issues nếu cần tổng hợp vấn đề.

Sau khi gọi tool, trả về DUY NHẤT một JSON object theo schema user yêu cầu.
Không trả markdown, không giải thích ngoài JSON.

{skill_contexts}
"""


def _called_tools_by_agent(metadata: dict[str, Any]) -> dict[str, list[str]]:
    called_tools = metadata.get("called_tools", [])
    if not isinstance(called_tools, list):
        return {}
    normalized = sorted({str(tool) for tool in called_tools if str(tool)})
    return {"SingleAgent": normalized} if normalized else {}


def _extract_agent_text(result: dict[str, Any]) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        return ""
    last_message = messages[-1]
    content = getattr(last_message, "content", last_message)
    return _content_to_text(content)


def _extract_called_tools(result: dict[str, Any]) -> list[str]:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    called: list[str] = []
    for message in messages:
        for tool_call in getattr(message, "tool_calls", []) or []:
            if isinstance(tool_call, dict) and tool_call.get("name"):
                called.append(str(tool_call["name"]))
        tool_name = getattr(message, "name", None)
        message_type = getattr(message, "type", "")
        if tool_name and message_type == "tool":
            called.append(str(tool_name))
    return sorted(set(called))


def _extract_token_usage_metadata(result: dict[str, Any]) -> dict[str, Any]:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    llm_call_count = 0

    for message in messages:
        usage = _message_usage_payload(message)
        if not usage:
            continue
        prompt, completion, total = _usage_counts(usage)
        if not any([prompt, completion, total]):
            continue
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total or prompt + completion
        llm_call_count += 1

    if not llm_call_count:
        return {}
    return {
        "usage_metadata": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "llm_call_count": llm_call_count,
    }


def _message_usage_payload(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage

    response_metadata = getattr(message, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return {}
    for key in ["usage_metadata", "token_usage", "usage"]:
        value = response_metadata.get(key)
        if isinstance(value, dict):
            return value
    return response_metadata


def _usage_counts(usage: dict[str, Any]) -> tuple[int, int, int]:
    prompt_tokens = _first_usage_int(
        usage,
        ["input_tokens", "prompt_tokens", "prompt_token_count", "input_token_count"],
    )
    completion_tokens = _first_usage_int(
        usage,
        [
            "output_tokens",
            "completion_tokens",
            "candidates_token_count",
            "output_token_count",
            "completion_token_count",
        ],
    )
    total_tokens = _first_usage_int(usage, ["total_tokens", "total_token_count"])
    return prompt_tokens, completion_tokens, total_tokens


def _first_usage_int(payload: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return 0


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content).strip()


def _load_ocr_evidence(
    claim: dict[str, Any],
    ocr_cache_dir: Path,
    *,
    ocr_source: str,
    mongo_url: str | None,
    mongo_db: str | None,
) -> dict[str, Any]:
    claim_id = str(claim.get("claim_id", ""))
    if ocr_source in {"auto", "mongo"}:
        mongo_evidence = _load_mongo_ocr_cache(claim, mongo_url, mongo_db)
        if mongo_evidence.get("ocr_cache_status") == "found":
            return mongo_evidence
        if ocr_source == "mongo":
            return mongo_evidence

    return _load_file_ocr_cache(ocr_cache_dir, claim_id)


def _load_mongo_ocr_cache(
    claim: dict[str, Any],
    mongo_url: str | None,
    mongo_db: str | None,
) -> dict[str, Any]:
    claim_id = str(claim.get("claim_id", ""))
    file_hash = str(claim.get("file_hash") or "")
    if not claim_id and not file_hash:
        return {
            "ocr_cache_status": "missing",
            "ocr_cache_source": "mongo",
            "note": "Claim has no claim_id or file_hash for Mongo OCR lookup.",
        }

    try:
        from pymongo import MongoClient
    except ImportError:
        return {
            "ocr_cache_status": "missing",
            "ocr_cache_source": "mongo",
            "note": "pymongo is not installed.",
        }

    query_terms: list[dict[str, str]] = []
    if claim_id:
        query_terms.append({"claim_id": claim_id})
    if file_hash:
        query_terms.append({"file_hash": file_hash})

    query = {"$or": query_terms} if len(query_terms) > 1 else query_terms[0]
    projection = {
        "_id": 0,
        "run_id": 1,
        "claim_id": 1,
        "file_hash": 1,
        "ocr_version": 1,
        "ocr_stage": 1,
        "ocr_pipeline": 1,
        "ocr_model": 1,
        "cache_identity": 1,
        "cache_status": 1,
        "source_document_id": 1,
        "created_at": 1,
        "ocr_result": 1,
    }

    client = None
    try:
        client = MongoClient(
            _normalize_mongo_url(mongo_url or DEFAULT_MONGODB_URL),
            serverSelectionTimeoutMS=5000,
        )
        documents = list(
            client[mongo_db or DEFAULT_MONGODB_DB]["documents"]
            .find(query, projection)
            .sort("created_at", -1)
            .limit(50)
        )
    except Exception as exc:
        return {
            "ocr_cache_status": "missing",
            "ocr_cache_source": "mongo",
            "note": f"Mongo OCR lookup failed: {exc}",
        }
    finally:
        if client is not None:
            with suppress(Exception):
                client.close()

    selected = _select_ocr_document(documents)
    if not selected:
        return {
            "ocr_cache_status": "missing",
            "ocr_cache_source": "mongo",
            "note": "No OCR document found in Mongo for claim_id/file_hash.",
            "claim_id": claim_id,
            "file_hash": file_hash,
        }

    created_at = selected.get("created_at")
    if created_at is not None:
        selected["created_at"] = str(created_at)
    cache_key = ":".join(
        item
        for item in [
            "mongo",
            str(selected.get("claim_id") or claim_id),
            str(selected.get("file_hash") or file_hash),
            str(selected.get("ocr_stage") or ""),
            str(selected.get("cache_identity") or ""),
        ]
        if item
    )
    return {
        "ocr_cache_status": "found",
        "ocr_cache_source": "mongo",
        "ocr_cache_key": cache_key,
        "ocr_metadata": {key: value for key, value in selected.items() if key != "ocr_result"},
        "ocr_payload": selected.get("ocr_result", {}),
    }


def _select_ocr_document(documents: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not documents:
        return None
    stage_rank = {stage: index for index, stage in enumerate(PREFERRED_OCR_STAGES)}
    return min(
        documents,
        key=lambda item: stage_rank.get(str(item.get("ocr_stage") or ""), len(stage_rank)),
    )


def _load_file_ocr_cache(ocr_cache_dir: Path, claim_id: str) -> dict[str, Any]:
    path = ocr_cache_dir / f"{claim_id}.json"
    if not path.exists():
        return {
            "ocr_cache_status": "missing",
            "ocr_cache_source": "file",
            "note": (
                "No OCR cache snapshot found for this claim. PDF text fallback should be "
                "used from claim metadata."
            ),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "ocr_cache_status": "found",
        "ocr_cache_source": "file",
        "ocr_cache_key": f"file:{claim_id}",
        "ocr_cache_file": str(path),
        "ocr_payload": payload,
    }


def _normalize_mongo_url(mongo_url: str) -> str:
    if "directConnection" in mongo_url:
        return mongo_url
    separator = "&" if "?" in mongo_url else "?"
    return f"{mongo_url}{separator}directConnection=true"


def _extract_pdf_text(file_path: Any, max_chars: int = 20000) -> str:
    return extract_pdf_text(file_path, max_chars=max_chars)


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if "```json" in stripped:
        stripped = stripped.split("```json", 1)[1].split("```", 1)[0].strip()
    elif stripped.startswith("```"):
        stripped = stripped.split("```", 1)[1].split("```", 1)[0].strip()
    if not stripped.startswith("{") and "{" in stripped:
        stripped = stripped[stripped.find("{") :]
    if not stripped.endswith("}") and "}" in stripped:
        stripped = stripped[: stripped.rfind("}") + 1]
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Baseline LLM response must be a JSON object.")
    return parsed
