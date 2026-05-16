import json
from pathlib import Path

from eval.baseline import (
    _extract_token_usage_metadata,
    _parse_json_object,
    _select_ocr_document,
    build_baseline_prompt,
    run_baseline,
)


class StaticBaselineAdapter:
    def __init__(self, payload: dict, metadata: dict | None = None) -> None:
        self.payload = payload
        self.metadata = metadata or {}
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        raw_text = json.dumps(self.payload, ensure_ascii=False)
        return self.payload, raw_text, self.metadata


class FakeMessage:
    def __init__(self, usage_metadata=None, response_metadata=None) -> None:
        self.usage_metadata = usage_metadata
        self.response_metadata = response_metadata or {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_baseline_prompt_uses_claim_and_ocr_cache(tmp_path: Path):
    ocr_cache = tmp_path / "ocr"
    _write_json(ocr_cache / "CLAIM-001.json", {"documents": [{"document_code": "invoice"}]})

    prompt, cache_key = build_baseline_prompt(
        {
            "claim_id": "CLAIM-001",
            "file_name": "a.pdf",
            "file_path": "data/a.pdf",
            "category_code": "OP_ILL",
        },
        ocr_cache,
        ocr_source="file",
    )

    assert cache_key == "file:CLAIM-001"
    assert "CLAIM-001" in prompt
    assert "invoice" in prompt
    assert "final_decision" in prompt
    assert "quality_assessment" in prompt
    assert "medical_findings" in prompt
    assert "medicine_mismatch" in prompt


def test_run_baseline_writes_single_agent_experiment_result(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    results_dir = tmp_path / "single"
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
            "results_dir": results_dir,
            "ocr_cache_dir": tmp_path / "ocr",
            "ocr_source": "file",
            "mongo_url": "",
            "mongo_db": "",
            "require_ocr_cache": False,
            "allow_pdf_fallback": False,
            "model": "gemini-test",
            "limit": None,
            "claim_id": None,
            "skip_existing": False,
            "dry_run": False,
        },
    )()
    adapter = StaticBaselineAdapter(
        {"final_decision": "accept", "missing_docs": [], "quality_issues": []},
        {
            "usage_metadata": {"input_tokens": 10, "output_tokens": 5},
            "called_tools": ["check-icd", "validate-medication", "check-icd"],
        },
    )

    results = run_baseline(args, adapter=adapter)
    saved = json.loads((results_dir / "CLAIM-001.json").read_text(encoding="utf-8"))

    assert len(results) == 1
    assert saved["mode"] == "single_agent"
    assert saved["final_decision"] == "accept"
    assert saved["agent_outputs"]["single_agent"]["final_decision"] == "accept"
    assert saved["prompt_tokens"] == 10
    assert saved["completion_tokens"] == 5
    assert saved["token_usage"] == 15
    assert saved["token_usage_source"] == "provider_metadata"
    assert saved["model_name"] == "gemini-test"
    assert saved["called_tools_by_agent"] == {"SingleAgent": ["check-icd", "validate-medication"]}


def test_run_baseline_skip_existing_does_not_call_adapter(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    results_dir = tmp_path / "single"
    _write_json(
        ground_truth,
        {"metadata": {}, "claims": [{"claim_id": "CLAIM-001", "file_path": "data/a.pdf"}]},
    )
    _write_json(
        results_dir / "CLAIM-001.json",
        {
            "claim_id": "CLAIM-001",
            "mode": "single_agent",
            "agent_outputs": {"single_agent": {"final_decision": "reject"}},
            "final_decision": "reject",
        },
    )
    args = type(
        "Args",
        (),
        {
            "ground_truth": ground_truth,
            "results_dir": results_dir,
            "ocr_cache_dir": tmp_path / "ocr",
            "ocr_source": "file",
            "mongo_url": "",
            "mongo_db": "",
            "require_ocr_cache": False,
            "allow_pdf_fallback": False,
            "model": "gemini-test",
            "limit": None,
            "claim_id": None,
            "skip_existing": True,
            "dry_run": False,
        },
    )()
    adapter = StaticBaselineAdapter({"final_decision": "accept"})

    results = run_baseline(args, adapter=adapter)

    assert results[0].final_decision == "reject"
    assert adapter.prompts == []


def test_select_ocr_document_prefers_phase2_over_newer_phase1():
    selected = _select_ocr_document(
        [
            {"ocr_stage": "phase1_classified", "created_at": "newer"},
            {"ocr_stage": "phase2_extracted", "created_at": "older"},
        ]
    )

    assert selected == {"ocr_stage": "phase2_extracted", "created_at": "older"}


def test_parse_json_object_extracts_fenced_json():
    parsed = _parse_json_object('extra\n```json\n{"final_decision": "accept"}\n```\ntext')

    assert parsed == {"final_decision": "accept"}


def test_extract_token_usage_metadata_sums_agent_model_calls():
    metadata = _extract_token_usage_metadata(
        {
            "messages": [
                FakeMessage({"input_tokens": 10, "output_tokens": 3, "total_tokens": 13}),
                FakeMessage(
                    response_metadata={
                        "usage_metadata": {
                            "prompt_token_count": 20,
                            "candidates_token_count": 5,
                            "total_token_count": 25,
                        }
                    }
                ),
                object(),
            ]
        }
    )

    assert metadata == {
        "usage_metadata": {
            "input_tokens": 30,
            "output_tokens": 8,
            "total_tokens": 38,
        },
        "llm_call_count": 2,
    }
