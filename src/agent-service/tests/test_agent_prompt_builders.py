"""Tests for agent prompt builder helpers."""

from agents.prompt_builders import (
    build_completeness_prompt,
    build_decision_prompt,
    build_schema_output_instruction,
    build_verifier_prompt,
)
from schemas.agent_outputs import AssessmentOutput


def test_completeness_prompt_includes_claim_context_and_history():
    prompt = build_completeness_prompt(
        {
            "claim_id": "CLAIM-001",
            "policy_number": "POL-001",
            "input_file": "claim.pdf",
            "extracted_documents": {
                "ocr_stage": "phase1_classified",
                "documents": [{"document_code": "invoice"}],
            },
            "history": [{"step": "ocr", "agent": "System"}],
        }
    )

    assert "CLAIM-001" in prompt
    assert "POL-001" in prompt
    assert "<ocr_stage>" in prompt
    assert "phase1_classified" in prompt
    assert "invoice" in prompt
    assert "<extracted_documents>" in prompt
    assert "Bước ocr" in prompt


def test_decision_prompt_uses_agent_results_not_raw_ocr():
    prompt = build_decision_prompt(
        {
            "claim_id": "CLAIM-001",
            "policy_number": "POL-001",
            "agent_1_result": {"decision": "accept"},
            "agent_2_result": {"decision": "reject"},
            "extracted_documents": {"raw": "should not be included"},
        }
    )

    assert "<completeness_result>" in prompt
    assert "<quality_result>" in prompt
    assert "should not be included" not in prompt


def test_verifier_prompt_selects_completeness_result_from_current_step():
    prompt = build_verifier_prompt(
        {
            "claim_id": "CLAIM-001",
            "input_file": "claim.pdf",
            "current_step": "completed_completeness_agent",
            "agent_1_result": {"decision": "reject", "evidence": {"missing": ["invoice"]}},
            "agent_2_result": {"decision": "accept"},
            "extracted_documents": {},
        }
    )

    assert '"missing"' in prompt
    assert '"decision": "reject"' in prompt


def test_verifier_prompt_prefers_explicit_review_stage():
    prompt = build_verifier_prompt(
        {
            "claim_id": "CLAIM-001",
            "input_file": "claim.pdf",
            "review_stage": "completeness",
            "current_step": "completed_quality_agent",
            "agent_1_result": {"decision": "reject", "evidence": {"missing": ["invoice"]}},
            "agent_2_result": {"decision": "accept"},
            "extracted_documents": {},
        }
    )

    assert '"missing"' in prompt
    assert '"decision": "reject"' in prompt


def test_schema_instruction_excludes_internal_auto_review_field():
    instruction = build_schema_output_instruction(AssessmentOutput)

    assert "<output_format>" in instruction
    assert "is_auto_reviewed" not in instruction
