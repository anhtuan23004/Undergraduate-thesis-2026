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
