import json
from pathlib import Path

from eval.ground_truth import clean_ground_truth_file, clean_ground_truth_payload


def test_clean_ground_truth_removes_fake_metadata_and_resets_seeded_labels():
    payload = {
        "metadata": {
            "total_claims": 2,
            "labeling_mode": "fake_ground_truth_for_metric_smoke_test",
            "fake_label_count": 1,
            "fake_label_warning": "Temporary labels generated from agent outputs",
        },
        "claims": [
            {
                "claim_id": "CLAIM-001",
                "file_name": "a.pdf",
                "file_path": "data/a.pdf",
                "category_code": "OP_ILL",
                "expected_decision": "accept",
                "expected_missing_docs": ["MISSING_DOC"],
                "expected_icd_codes": ["I10"],
                "expected_exclusions": ["waiting_period"],
                "expected_quality_issues": ["ICD_MISSING"],
                "expected_routing_path": ["completeness_check"],
                "label_status": "final",
                "expert_notes": "Temporary fake label",
            },
            {
                "claim_id": "CLAIM-002",
                "file_name": "b.pdf",
                "file_path": "data/b.pdf",
                "category_code": "OP_ILL",
                "label_status": "unlabeled",
            },
        ],
    }

    cleaned, stats = clean_ground_truth_payload(payload)

    assert "labeling_mode" not in cleaned["metadata"]
    assert "fake_label_count" not in cleaned["metadata"]
    assert stats == {"removed_metadata_count": 3, "reset_label_count": 1, "claim_count": 2}
    assert cleaned["claims"][0]["expected_decision"] == ""
    assert cleaned["claims"][0]["expected_missing_docs"] == []
    assert cleaned["claims"][0]["expected_icd_codes"] == []
    assert cleaned["claims"][0]["expected_exclusions"] == []
    assert cleaned["claims"][0]["expected_quality_issues"] == []
    assert cleaned["claims"][0]["expected_routing_path"] == []
    assert cleaned["claims"][0]["label_status"] == "unlabeled"
    assert cleaned["claims"][0]["expert_notes"] == ""
    assert cleaned["claims"][0]["claim_id"] == "CLAIM-001"
    assert cleaned["claims"][0]["file_path"] == "data/a.pdf"


def test_clean_ground_truth_file_writes_clean_manifest(tmp_path: Path):
    manifest = tmp_path / "ground_truth.json"
    manifest.write_text(
        json.dumps(
            {
                "metadata": {"fake_label_source": "eval/results/suggestions/*.json"},
                "claims": [{"claim_id": "CLAIM-001", "label_status": "unlabeled"}],
            }
        ),
        encoding="utf-8",
    )

    stats = clean_ground_truth_file(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert stats["removed_metadata_count"] == 1
    assert payload["metadata"] == {}
    assert payload["claims"][0]["claim_id"] == "CLAIM-001"
