"""Contract tests for OCR service v2 API wiring and schemas."""

import pytest
from api.routes import ocr_router_v2, ocr_router_v2_form
from pydantic import ValidationError
from schemas import ExtractRequest
from utils.schema_builder import build_phase2_batch_response_schema


def _minimal_schema() -> dict:
    return {
        "document_code": "medical_report",
        "document_name": "Báo cáo y tế",
        "fields": [
            {
                "field_key": "patient_name",
                "data_type": "string",
            }
        ],
    }


def test_v2_router_prefixes_match_gemini_ocr_contract():
    assert ocr_router_v2.prefix == "/api/v2/ocr"
    assert ocr_router_v2_form.prefix == "/api/v2/ocr"


def test_extract_request_accepts_url_source():
    request = ExtractRequest(
        file_url="https://example.com/claim.pdf",
        extraction_schemas=[_minimal_schema()],
    )

    assert request.file_url == "https://example.com/claim.pdf"
    assert request.file_data is None


def test_extract_request_accepts_base64_source():
    request = ExtractRequest(
        file_data="JVBERi0xLjQ=",
        extraction_schemas=[_minimal_schema()],
    )

    assert request.file_data == "JVBERi0xLjQ="
    assert request.file_url is None


@pytest.mark.parametrize(
    "payload",
    [
        {"extraction_schemas": [_minimal_schema()]},
        {
            "file_url": "https://example.com/claim.pdf",
            "file_data": "JVBERi0xLjQ=",
            "extraction_schemas": [_minimal_schema()],
        },
    ],
)
def test_extract_request_requires_exactly_one_file_source(payload):
    with pytest.raises(ValidationError):
        ExtractRequest(**payload)


def test_phase2_batch_schema_wraps_single_document_schema():
    schema = build_phase2_batch_response_schema(
        ExtractRequest(
            file_url="https://example.com/claim.pdf",
            extraction_schemas=[_minimal_schema()],
        ).extraction_schemas[0]
    )

    assert schema["type"] == "array"
    assert schema["items"]["type"] == "object"
    assert "patient_name" in schema["items"]["properties"]
