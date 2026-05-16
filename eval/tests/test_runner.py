import json
from pathlib import Path

from eval.runner import summarize
from eval.schemas import ExperimentResult


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_summarize_uses_ground_truth_labels_by_default(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    results_dir = tmp_path / "claims"
    output_dir = tmp_path / "results"
    _write_json(
        ground_truth,
        {
            "metadata": {},
            "claims": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "accept",
                    "label_status": "final",
                }
            ],
        },
    )
    _write_json(
        results_dir / "CLAIM-001.json",
        ExperimentResult(
            claim_id="CLAIM-001", mode="multi_agent", final_decision="accept"
        ).to_dict(),
    )

    summary = summarize(
        ground_truth_path=ground_truth,
        multi_results_path=results_dir,
        output_dir=output_dir,
    )

    assert summary["label_source"] == str(ground_truth)
    assert summary["labelled_claim_count"] == 1
    assert summary["by_mode"]["multi_agent"]["decision"]["accuracy"] == 1.0


def test_summarize_allows_explicit_review_label_override(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    reviewed_labels = tmp_path / "reviewed_labels.json"
    results_dir = tmp_path / "claims"
    output_dir = tmp_path / "results"
    _write_json(
        ground_truth,
        {
            "metadata": {},
            "claims": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "accept",
                    "label_status": "final",
                }
            ],
        },
    )
    _write_json(
        reviewed_labels,
        {
            "labels": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "reject",
                    "label_status": "final",
                }
            ]
        },
    )
    _write_json(
        results_dir / "CLAIM-001.json",
        ExperimentResult(
            claim_id="CLAIM-001", mode="multi_agent", final_decision="reject"
        ).to_dict(),
    )

    summary = summarize(
        ground_truth_path=ground_truth,
        multi_results_path=results_dir,
        output_dir=output_dir,
        labels_path=reviewed_labels,
    )

    assert summary["label_source"] == str(reviewed_labels)
    assert summary["by_mode"]["multi_agent"]["decision"]["accuracy"] == 1.0


def test_summarize_writes_research_question_summary_and_not_observed_tools(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    reviewed_labels = tmp_path / "reviewed_labels.json"
    results_dir = tmp_path / "claims"
    output_dir = tmp_path / "results"
    _write_json(
        ground_truth,
        {
            "metadata": {},
            "claims": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "",
                    "label_status": "unlabeled",
                }
            ],
        },
    )
    _write_json(
        reviewed_labels,
        {
            "labels": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "reject",
                    "expected_missing_docs": ["MISSING_DOC"],
                    "expected_quality_issues": ["ICD_MISSING"],
                    "expected_icd_codes": ["I10"],
                    "expected_exclusions": [],
                    "expected_routing_path": ["completeness_check", "quality_check"],
                    "expected_tools_by_agent": {"CompletenessAgent": ["check-required-docs"]},
                    "label_status": "final",
                }
            ]
        },
    )
    _write_json(
        results_dir / "CLAIM-001.json",
        ExperimentResult(
            claim_id="CLAIM-001",
            mode="multi_agent",
            final_decision="reject",
            routing_path=["completeness_check", "quality_check"],
            called_tools_by_agent={},
            agent_outputs={
                "CompletenessAgent": {
                    "issues": [{"code": "MISSING_DOC"}],
                },
                "QualityAgent": {
                    "issues": [{"code": "ICD_MISSING"}],
                    "evidence": {"icd_codes": ["I10"]},
                },
            },
        ).to_dict(),
    )

    summary = summarize(
        ground_truth_path=ground_truth,
        multi_results_path=results_dir,
        output_dir=output_dir,
        labels_path=reviewed_labels,
    )

    assert summary["research_questions"]["RQ1"]["metrics"]["accuracy"] == 1.0
    assert summary["research_questions"]["RQ2"]["metrics"]["f1"] == 1.0
    assert summary["research_questions"]["RQ3"]["metrics"]["icd_detection"]["f1"] == 1.0
    assert summary["research_questions"]["RQ4"]["metrics"]["tool_usage"] == {
        "status": "not_observed"
    }
    assert summary["research_questions"]["RQ4"]["metrics"]["invalid_tool_call_rate"] == (
        "not_observed"
    )
    assert (output_dir / "rq_report.md").exists()


def test_summarize_computes_paired_rq5_comparison(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    reviewed_labels = tmp_path / "reviewed_labels.json"
    multi_dir = tmp_path / "multi"
    single_dir = tmp_path / "single"
    output_dir = tmp_path / "results"
    _write_json(
        ground_truth,
        {"metadata": {}, "claims": [{"claim_id": "CLAIM-001", "label_status": "unlabeled"}]},
    )
    _write_json(
        reviewed_labels,
        {
            "labels": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "accept",
                    "label_status": "final",
                }
            ]
        },
    )
    _write_json(
        multi_dir / "CLAIM-001.json",
        ExperimentResult(
            claim_id="CLAIM-001",
            mode="multi_agent",
            final_decision="accept",
            latency_ms=10,
            token_usage=100,
        ).to_dict(),
    )
    _write_json(
        single_dir / "CLAIM-001.json",
        ExperimentResult(
            claim_id="CLAIM-001",
            mode="single_agent",
            final_decision="reject",
            latency_ms=20,
            token_usage=50,
        ).to_dict(),
    )

    summary = summarize(
        ground_truth_path=ground_truth,
        multi_results_path=multi_dir,
        single_results_path=single_dir,
        output_dir=output_dir,
        labels_path=reviewed_labels,
    )

    rq5 = summary["research_questions"]["RQ5"]
    assert rq5["status"] == "computed"
    assert rq5["paired_count"] == 1
    assert rq5["multi_agent"]["accuracy"] == 1.0
    assert rq5["single_agent"]["accuracy"] == 0.0
    assert rq5["delta"]["accuracy"] == 1.0


def test_summarize_reads_single_agent_nested_quality_assessment(tmp_path: Path):
    ground_truth = tmp_path / "ground_truth.json"
    reviewed_labels = tmp_path / "reviewed_labels.json"
    single_dir = tmp_path / "single"
    output_dir = tmp_path / "results"
    _write_json(
        ground_truth,
        {"metadata": {}, "claims": [{"claim_id": "CLAIM-001", "label_status": "unlabeled"}]},
    )
    _write_json(
        reviewed_labels,
        {
            "labels": [
                {
                    "claim_id": "CLAIM-001",
                    "expected_decision": "needs_review",
                    "expected_quality_issues": ["ICD_MISMATCH"],
                    "expected_icd_codes": ["K75"],
                    "label_status": "final",
                }
            ]
        },
    )
    _write_json(
        single_dir / "CLAIM-001.json",
        ExperimentResult(
            claim_id="CLAIM-001",
            mode="single_agent",
            final_decision="needs_review",
            agent_outputs={
                "single_agent": {
                    "quality_issues": [],
                    "icd_codes": [],
                    "quality_assessment": {
                        "issues": [{"code": "ICD_MISMATCH"}],
                        "evidence": {"icd_codes": [{"code": "K75", "diagnosis": "Tăng men gan"}]},
                    },
                }
            },
        ).to_dict(),
    )

    summary = summarize(
        ground_truth_path=ground_truth,
        single_results_path=single_dir,
        output_dir=output_dir,
        labels_path=reviewed_labels,
    )

    single = summary["by_mode"]["single_agent"]
    assert single["quality_issues"]["f1"] == 1.0
    assert single["icd_detection"]["f1"] == 1.0
