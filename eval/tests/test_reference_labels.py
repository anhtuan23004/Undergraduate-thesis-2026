import csv
import json
from pathlib import Path

from eval.reference_labels import (
    REFERENCE_LABEL_MODEL,
    build_reference_label_prompt,
    run_label_reference,
)


class StaticReferenceAdapter:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return self.payload, json.dumps(self.payload), {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_reference_label_prompt_uses_manifest_and_ocr_cache_not_agent_results(tmp_path: Path):
    ocr_cache = tmp_path / "ocr"
    _write_json(ocr_cache / "CLAIM-001.json", {"documents": [{"document_code": "invoice"}]})

    prompt = build_reference_label_prompt(
        {
            "claim_id": "CLAIM-001",
            "file_name": "a.pdf",
            "file_path": "data/a.pdf",
            "category_code": "OP_ILL",
            "final_decision": "reject",
        },
        ocr_cache,
    )

    assert "CLAIM-001" in prompt
    assert "invoice" in prompt
    assert "Không dùng kết quả agent" in prompt
    assert '"final_decision": "reject"' not in prompt


def test_reference_label_prompt_can_include_agent_results_and_pdf_text(tmp_path: Path):
    multi_results = tmp_path / "multi"
    single_results = tmp_path / "single"
    _write_json(
        multi_results / "CLAIM-001.json",
        {
            "mode": "multi_agent",
            "final_decision": "reject",
            "agent_outputs": {"QualityAgent": {"issues": [{"code": "ICD_MISMATCH"}]}},
            "called_tools_by_agent": {"QualityAgent": ["check-icd"]},
        },
    )
    _write_json(
        single_results / "CLAIM-001.json",
        {
            "mode": "single_agent",
            "final_decision": "needs_review",
            "agent_outputs": {"single_agent": {"quality_issues": ["ICD_MISMATCH"]}},
        },
    )

    prompt = build_reference_label_prompt(
        {
            "claim_id": "CLAIM-001",
            "file_name": "a.pdf",
            "file_path": "data/a.pdf",
            "category_code": "OP_ILL",
        },
        tmp_path / "ocr",
        include_agent_results=True,
        multi_results_dir=multi_results,
        single_results_dir=single_results,
    )

    assert "Bạn được xem output của multi-agent" in prompt
    assert '"final_decision": "reject"' in prompt
    assert "ICD_MISMATCH" in prompt
    assert "PDF text evidence" in prompt


def test_run_label_reference_writes_reviewed_labels_and_audit_queue(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    output = tmp_path / "reviewed_labels.json"
    audit_queue = tmp_path / "audit_queue.csv"
    _write_json(
        ground_truth,
        {
            "metadata": {},
            "claims": [
                {
                    "claim_id": "CLAIM-001",
                    "file_name": "a.pdf",
                    "file_path": "data/a.pdf",
                    "category_code": "OP_ILL",
                }
            ],
        },
    )
    args = type(
        "Args",
        (),
        {
            "ground_truth": ground_truth,
            "output": output,
            "audit_queue": audit_queue,
            "ocr_cache_dir": tmp_path / "ocr",
            "multi_results": tmp_path / "multi",
            "single_results": tmp_path / "single",
            "include_agent_results": True,
            "pdf_max_chars": 20000,
            "model": REFERENCE_LABEL_MODEL,
            "limit": None,
            "claim_id": None,
            "skip_existing": False,
            "dry_run": False,
        },
    )()
    adapter = StaticReferenceAdapter(
        {
            "expected_decision": "needs_review",
            "expected_missing_docs": ["medical_report"],
            "expected_icd_codes": ["I10"],
            "expected_medications": ["amlodipine"],
            "expected_exclusions": [],
            "expected_quality_issues": ["ICD_MISSING"],
            "expected_consistency_issues": [],
            "expected_routing_path": ["completeness_check", "quality_check"],
            "expected_tools_by_agent": {"CompletenessAgent": ["check-required-docs"]},
            "complexity": "ambiguous",
            "confidence": 0.6,
            "expert_notes": "Needs human audit.",
        }
    )

    payload = run_label_reference(args, adapter=adapter)
    saved = json.loads(output.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(audit_queue.open(encoding="utf-8")))

    assert payload["metadata"]["llm_model"] == REFERENCE_LABEL_MODEL
    assert saved["labels"][0]["claim_id"] == "CLAIM-001"
    assert saved["labels"][0]["label_status"] == "reviewed"
    assert saved["labels"][0]["label_source"] == "llm_judge_with_agent_outputs"
    assert saved["labels"][0]["reviewer"] == "gemini_judge"
    assert saved["labels"][0]["llm_model"] == REFERENCE_LABEL_MODEL
    assert rows[0]["claim_id"] == "CLAIM-001"
    assert "low_confidence" in rows[0]["reason"]
