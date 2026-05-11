"""Tests for OCR phase 2 extraction graph node."""

import pytest
from graphs.ocr_extraction import run_ocr_extraction


@pytest.mark.asyncio
async def test_ocr_extraction_node_runs_phase2(monkeypatch):
    class FakeOcrPipeline:
        def phase2_input_documents(self, extracted_documents):
            return [
                {
                    "document_code": doc["document_code"],
                    "start_page": doc["start_page"],
                    "end_page": doc["end_page"],
                }
                for doc in extracted_documents["documents"]
            ]

        async def prepare_phase2_ocr(
            self,
            run_id,
            claim_id,
            policy_number,
            input_file,
            phase1_documents,
            file_hash=None,
        ):
            assert run_id == "run-1"
            assert claim_id == "claim-1"
            assert policy_number == "policy-1"
            assert input_file == "claim.pdf"
            assert file_hash == "hash-1"
            return {
                "ocr_version": "v2",
                "ocr_stage": "phase2_extracted",
                "phase1_documents": phase1_documents,
                "documents": [
                    {
                        "document_code": "medical_report",
                        "extracted_data": {"diagnosis": "Viêm họng"},
                    }
                ],
            }

    monkeypatch.setattr(
        "graphs.ocr_extraction.get_default_ocr_pipeline",
        FakeOcrPipeline,
    )

    result = await run_ocr_extraction(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "policy_number": "policy-1",
            "input_file": "claim.pdf",
            "file_hash": "hash-1",
            "extracted_documents": {
                "ocr_stage": "phase1_classified",
                "documents": [
                    {
                        "document_code": "medical_report",
                        "start_page": 1,
                        "end_page": 1,
                    }
                ],
            },
        }
    )

    assert result["ocr_stage"] == "phase2_extracted"
    assert result["active_stage"] == "quality"
    assert result["current_step"] == "completed_ocr_extraction"
    assert (
        result["extracted_documents"]["documents"][0]["extracted_data"]["diagnosis"] == "Viêm họng"
    )


@pytest.mark.asyncio
async def test_ocr_extraction_node_returns_quality_reject_on_missing_phase1():
    result = await run_ocr_extraction(
        {
            "run_id": "run-1",
            "claim_id": "claim-1",
            "policy_number": "policy-1",
            "input_file": "claim.pdf",
            "file_hash": None,
            "extracted_documents": {
                "ocr_stage": "phase1_classified",
                "documents": [],
            },
        }
    )

    assert result["ocr_stage"] == "error"
    assert result["extracted_documents"]["ocr_stage"] == "error"
    assert result["extracted_documents"]["error"]["stage"] == "phase2_extraction"
    assert result["extracted_documents"]["error"]["code"] == "OCR_EXTRACTION_FAILED"
    assert result["agent_2_result"]["decision"] == "reject"
    assert result["agent_2_result"]["issues"][0]["code"] == "OCR_EXTRACTION_FAILED"
