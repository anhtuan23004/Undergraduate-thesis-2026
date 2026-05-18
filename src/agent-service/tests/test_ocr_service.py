"""Tests for OCR service helpers."""

import json
from pathlib import Path

import pytest
from config import Settings
from fastapi import HTTPException
from pydantic import ValidationError
from services.ocr_pipeline import (
    OcrCacheIdentity,
    OcrPipeline,
    initial_operation_spec,
    phase2_operation_spec,
    resolve_input_file_path,
)
from services.ocr_service import run_ocr_document, run_ocr_v2_extract


def test_resolve_input_file_path_accepts_relative_upload_path(monkeypatch, tmp_path):
    monkeypatch.setattr("services.ocr_pipeline.settings.UPLOADS_DIR", str(tmp_path))

    assert resolve_input_file_path("claim.pdf") == str(tmp_path / "claim.pdf")


def test_resolve_input_file_path_accepts_absolute_path_inside_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr("services.ocr_pipeline.settings.UPLOADS_DIR", str(tmp_path))
    input_path = tmp_path / "claim.pdf"

    assert resolve_input_file_path(str(input_path)) == str(input_path)


def test_resolve_input_file_path_rejects_path_outside_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr("services.ocr_pipeline.settings.UPLOADS_DIR", str(tmp_path))
    outside_path = Path(tmp_path).parent / "claim.pdf"

    with pytest.raises(HTTPException) as exc_info:
        resolve_input_file_path(str(outside_path))

    assert exc_info.value.status_code == 400


def test_resolve_input_file_path_rejects_empty_path(monkeypatch, tmp_path):
    monkeypatch.setattr("services.ocr_pipeline.settings.UPLOADS_DIR", str(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        resolve_input_file_path("")

    assert exc_info.value.status_code == 400


def test_settings_reject_unsupported_v2_pipeline():
    with pytest.raises(ValidationError):
        Settings(OCR_API_VERSION="v2", OCR_V2_PIPELINE="extract_full")


def test_run_ocr_document_uses_v2_classify_segment(monkeypatch, tmp_path):
    input_file = tmp_path / "claim.pdf"
    input_file.write_bytes(b"%PDF-1.4")
    captured = {}

    class FakeResponse:
        ok = True

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "documents": [
                    {
                        "document_code": "medical_report",
                        "document_name": "Giấy khám bệnh",
                        "start_page": 1,
                        "end_page": 1,
                    }
                ]
            }

    def fake_post(url, files, data, timeout):
        captured["url"] = url
        captured["files"] = files
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("services.ocr_pipeline.settings.UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_API_VERSION", "v2")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_SERVICE_URL", "http://ocr.local")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_TIMEOUT", 99)
    monkeypatch.setattr("services.ocr_pipeline.settings.OUTBOUND_HTTP_CONNECT_TIMEOUT", 3)
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_PIPELINE", "two_phase_gated")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_EXTRACT_ALL_FIELDS", False)
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_DOCUMENT_CODES", "")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_MODEL", "")
    monkeypatch.setattr("services.ocr_pipeline.requests.post", fake_post)

    result = run_ocr_document("claim.pdf")

    assert captured["url"] == "http://ocr.local/api/v2/ocr/classify-segment/form"
    assert captured["timeout"] == (3, 99)
    assert captured["files"]["file"][0] == "claim.pdf"
    assert "extract_all_fields" not in captured["data"]
    assert result["ocr_version"] == "v2"
    assert result["ocr_pipeline"] == "two_phase_gated"
    assert result["ocr_stage"] == "phase1_classified"
    assert result["document_codes"] == ["medical_report"]
    assert "phase1_documents" not in result
    assert "extracted_data" not in result["documents"][0]


def test_run_ocr_v2_extract_uses_phase1_documents(monkeypatch, tmp_path):
    input_file = tmp_path / "claim.pdf"
    input_file.write_bytes(b"%PDF-1.4")
    captured = {}
    phase1_documents = [
        {
            "document_code": "medical_report",
            "document_name": "Giấy khám bệnh",
            "start_page": 1,
            "end_page": 1,
        }
    ]

    class FakeResponse:
        ok = True

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "documents": [
                    {
                        "document_code": "medical_report",
                        "document_name": "Giấy khám bệnh",
                        "start_page": 1,
                        "end_page": 1,
                        "extracted_data": {"diagnosis": "Viêm họng"},
                    }
                ]
            }

    def fake_post(url, files, data, timeout):
        captured["url"] = url
        captured["files"] = files
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("services.ocr_pipeline.settings.UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_SERVICE_URL", "http://ocr.local")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_TIMEOUT", 99)
    monkeypatch.setattr("services.ocr_pipeline.settings.OUTBOUND_HTTP_CONNECT_TIMEOUT", 3)
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_PIPELINE", "two_phase_gated")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_EXTRACT_ALL_FIELDS", False)
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_DOCUMENT_CODES", "")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_MODEL", "")
    monkeypatch.setattr("services.ocr_pipeline.requests.post", fake_post)

    result = run_ocr_v2_extract("claim.pdf", phase1_documents)

    assert captured["url"] == "http://ocr.local/api/v2/ocr/extract/form"
    assert captured["timeout"] == (3, 99)
    assert captured["files"]["file"][0] == "claim.pdf"
    assert json.loads(captured["data"]["documents"]) == phase1_documents
    assert captured["data"]["extract_all_fields"] == "false"
    assert result["ocr_pipeline"] == "two_phase_gated"
    assert result["ocr_stage"] == "phase2_extracted"
    assert result["phase1_documents"] == phase1_documents
    assert result["documents"][0]["extracted_data"]["diagnosis"] == "Viêm họng"


@pytest.mark.asyncio
async def test_ocr_pipeline_cache_is_scoped_by_operation_identity(monkeypatch):
    calls = {}
    saved = []

    class FakeCollection:
        def find_one(self, query):
            calls["query"] = query
            return {
                "ocr_result": {
                    "ocr_version": "v2",
                    "ocr_pipeline": "two_phase_gated",
                    "ocr_stage": "phase1_classified",
                    "documents": [],
                }
            }

    def fake_save_ocr_result(*args, **kwargs):
        saved.append((args, kwargs))

    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_API_VERSION", "v2")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_PIPELINE", "two_phase_gated")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_DOCUMENT_CODES", "medical_report")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_MODEL", "gemini-test")
    operation = initial_operation_spec()
    cache_identity = OcrCacheIdentity("hash-1", operation)
    pipeline = OcrPipeline(
        collection_provider=lambda name: FakeCollection(),
        audit_writer=fake_save_ocr_result,
    )

    result = await pipeline.prepare_initial_ocr(
        "run-1",
        "claim-1",
        "policy-1",
        "claim.pdf",
        file_hash="hash-1",
    )

    assert calls["query"] == {
        "file_hash": "hash-1",
        "ocr_version": "v2",
        "ocr_stage": "phase1_classified",
        "ocr_pipeline": "two_phase_gated",
        "cache_identity": cache_identity.fingerprint,
        "$or": [
            {"cache_status": {"$exists": False}},
            {"cache_status": "created"},
        ],
    }
    assert result == {
        "ocr_version": "v2",
        "ocr_pipeline": "two_phase_gated",
        "ocr_stage": "phase1_classified",
        "documents": [],
    }
    assert saved[0][0][-4:] == ("v2", "phase1_classified", "reused", None)
    assert saved[0][1]["operation"] == operation
    assert saved[0][1]["cache_identity"] == cache_identity


@pytest.mark.asyncio
async def test_ocr_pipeline_uses_fake_adapter_when_cache_misses(monkeypatch):
    saved = []

    class EmptyCollection:
        def find_one(self, query):
            return None

    class FakeAdapter:
        def run_document(self, file_path):
            assert file_path == "claim.pdf"
            return {
                "ocr_version": "v2",
                "ocr_pipeline": "two_phase_gated",
                "ocr_stage": "phase1_classified",
                "documents": [{"document_code": "medical_report"}],
            }

        def run_phase2_extract(self, file_path, phase1_documents):
            raise AssertionError("phase 2 should not be called")

    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_API_VERSION", "v2")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_PIPELINE", "two_phase_gated")

    def fake_audit(*args, **kwargs):
        saved.append((args, kwargs))

    pipeline = OcrPipeline(
        adapter=FakeAdapter(),
        collection_provider=lambda name: EmptyCollection(),
        audit_writer=fake_audit,
    )

    result = await pipeline.prepare_initial_ocr(
        "run-1",
        "claim-1",
        "policy-1",
        "claim.pdf",
        file_hash="hash-1",
    )

    assert result["documents"] == [{"document_code": "medical_report"}]
    assert saved[0][0][-4:] == ("v2", "phase1_classified", "created", None)
    assert saved[0][1]["cache_identity"].fingerprint == saved[0][1]["operation"].fingerprint()


def test_phase2_operation_spec_fingerprints_phase1_documents(monkeypatch):
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_PIPELINE", "two_phase_gated")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_EXTRACT_ALL_FIELDS", False)
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_DOCUMENT_CODES", "medical_report")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_MODEL", "gemini-test")

    first = phase2_operation_spec(
        [
            {
                "document_code": "medical_report",
                "start_page": 1,
                "end_page": 1,
            }
        ]
    )
    second = phase2_operation_spec(
        [
            {
                "document_code": "medical_report",
                "start_page": 2,
                "end_page": 2,
            }
        ]
    )

    assert first.source_documents_fingerprint != second.source_documents_fingerprint
    assert first.fingerprint() != second.fingerprint()


def test_ocr_pipeline_builds_phase2_input_documents():
    pipeline = OcrPipeline()

    result = pipeline.phase2_input_documents(
        {
            "documents": [
                {
                    "document_code": "medical_report",
                    "document_name": "Giấy khám bệnh",
                    "start_page": 1,
                    "end_page": 1,
                    "page_ranges": [[1, 1], [3, 3]],
                    "page_order": [1, 3],
                    "duplicate_pages": [{"page": 2, "duplicate_of": 1}],
                    "extracted_data": {"diagnosis": "Viêm họng"},
                },
                "invalid",
            ]
        }
    )

    assert result == [
        {
            "document_code": "medical_report",
            "document_name": "Giấy khám bệnh",
            "start_page": 1,
            "end_page": 1,
            "page_ranges": [[1, 1], [3, 3]],
            "page_order": [1, 3],
            "duplicate_pages": [{"page": 2, "duplicate_of": 1}],
        }
    ]


def test_phase2_operation_spec_fingerprints_page_aware_documents(monkeypatch):
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_PIPELINE", "two_phase_gated")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_EXTRACT_ALL_FIELDS", False)
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_DOCUMENT_CODES", "medical_report")
    monkeypatch.setattr("services.ocr_pipeline.settings.OCR_V2_MODEL", "gemini-test")

    first = phase2_operation_spec(
        [
            {
                "document_code": "medical_report",
                "start_page": 1,
                "end_page": 3,
                "page_ranges": [[1, 1], [3, 3]],
                "page_order": [1, 3],
                "duplicate_pages": [],
            }
        ]
    )
    second = phase2_operation_spec(
        [
            {
                "document_code": "medical_report",
                "start_page": 1,
                "end_page": 3,
                "page_ranges": [[3, 3], [1, 1]],
                "page_order": [3, 1],
                "duplicate_pages": [],
            }
        ]
    )

    assert first.source_documents_fingerprint != second.source_documents_fingerprint
    assert first.fingerprint() != second.fingerprint()
