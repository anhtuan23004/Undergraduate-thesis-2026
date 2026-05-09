from pathlib import Path

from eval.labeling import (
    filter_claims,
    label_draft_for_claim,
    label_progress,
    load_agent_suggestions,
    load_reviewed_labels,
    parse_lines,
    parse_tools_json,
    save_json_atomic,
    save_reviewed_label,
    suggestion_to_label_updates,
    validate_claim_label,
)


def test_parse_lines_accepts_commas_and_newlines():
    assert parse_lines("invoice, receipt\ninvoice\n medical_report ") == [
        "invoice",
        "receipt",
        "medical_report",
    ]


def test_validate_final_label_requires_decision_routing_and_notes():
    errors = validate_claim_label({"label_status": "final"})

    assert "Final labels require expected_decision." in errors
    assert "Final labels require expected_routing_path." in errors
    assert "Final labels require expert_notes for auditability." in errors


def test_parse_tools_json_requires_agent_lists():
    parsed = parse_tools_json('{"CompletenessAgent": ["check-required-docs"]}')

    assert parsed == {"CompletenessAgent": ["check-required-docs"]}


def test_filter_claims_by_review_status():
    claims = [
        {"claim_id": "A", "category_code": "OP_ILL", "label_status": "reviewed"},
        {"claim_id": "B", "category_code": "IP_ILL", "label_status": "final"},
    ]

    assert label_progress(claims)["reviewed"] == 1
    assert [claim["claim_id"] for claim in filter_claims(claims, status="reviewed")] == ["A"]


def test_save_json_atomic(tmp_path: Path):
    path = tmp_path / "labels.json"

    save_json_atomic(path, {"labels": [{"claim_id": "A"}]})

    assert path.read_text(encoding="utf-8").endswith("\n")


def test_load_agent_suggestions_and_convert_to_label_updates(tmp_path: Path):
    path = tmp_path / "agent_suggestions.json"
    path.write_text(
        """
        {
          "suggestions": [
            {
              "claim_id": "A",
              "final_decision": "approve",
              "missing_docs": ["invoice"],
              "icd_codes": ["J06.9"],
              "exclusions": [],
              "quality_issues": ["icd_missing"],
              "routing_path": ["completeness_check"],
              "called_tools_by_agent": {"CompletenessAgent": ["check-required-docs"]}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    suggestions = load_agent_suggestions(path)
    updates = suggestion_to_label_updates(suggestions["A"])

    assert updates["expected_decision"] == "accept"
    assert updates["expected_missing_docs"] == ["invoice"]
    assert updates["expected_icd_codes"] == ["J06.9"]


def test_save_reviewed_label_does_not_mutate_dataset(tmp_path: Path):
    path = tmp_path / "reviewed_labels.json"
    claim = {
        "claim_id": "A",
        "file_name": "a.pdf",
        "file_path": "data/a.pdf",
        "category_code": "OP_ILL",
    }

    save_reviewed_label(path, claim, {"expected_decision": "accept", "label_status": "reviewed"})
    labels = load_reviewed_labels(path)

    assert labels["A"]["file_name"] == "a.pdf"
    assert labels["A"]["expected_decision"] == "accept"


def test_label_draft_prefers_reviewed_label_over_suggestion():
    claim = {"claim_id": "A", "expected_decision": ""}
    suggestion = {"final_decision": "reject"}
    reviewed = {"claim_id": "A", "expected_decision": "accept"}

    draft = label_draft_for_claim(claim, suggestion, reviewed)

    assert draft["expected_decision"] == "accept"
