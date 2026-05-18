"""Contract tests for OCR service v2 API wiring and schemas."""

import pytest
from api.routes import ocr_router_v2, ocr_router_v2_form
from pydantic import ValidationError
from schemas import (
    ClassificationSchema,
    ClassifySegmentRequest,
    ExtractFullRequest,
    ExtractRequest,
    SchemaSelectionError,
    load_default_extraction_schemas,
    resolve_default_extraction_schemas,
    to_classification_schemas,
)
from utils.schema_builder import build_phase1_response_schema


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


def _classified_document() -> dict:
    return {
        "document_code": "medical_report",
        "document_name": "Báo cáo y tế",
        "start_page": 1,
        "end_page": 1,
    }


def test_v2_router_prefixes_match_gemini_ocr_contract():
    assert ocr_router_v2.prefix == "/api/v2/ocr"
    assert ocr_router_v2_form.prefix == "/api/v2/ocr"
    assert any(route.path == "/api/v2/ocr/extract-full" for route in ocr_router_v2.routes)


def test_phase1_response_schema_requires_page_aware_metadata():
    schema = build_phase1_response_schema(
        [
            ClassificationSchema(
                document_code="medical_report",
                document_name="Báo cáo y tế",
            )
        ]
    )
    document_schema = schema["properties"]["documents"]["items"]

    assert "page_ranges" in document_schema["properties"]
    assert "page_order" in document_schema["properties"]
    assert "duplicate_pages" in document_schema["properties"]
    assert "page_ranges" in document_schema["required"]
    assert "page_order" in document_schema["required"]
    assert "duplicate_pages" in document_schema["required"]


def test_extract_request_accepts_url_source():
    request = ExtractRequest(
        file_url="https://example.com/claim.pdf",
        documents=[_classified_document()],
        extraction_schemas=[_minimal_schema()],
    )

    assert request.file_url == "https://example.com/claim.pdf"
    assert request.file_data is None


def test_extract_request_accepts_base64_source():
    request = ExtractRequest(
        file_data="JVBERi0xLjQ=",
        documents=[_classified_document()],
        extraction_schemas=[_minimal_schema()],
    )

    assert request.file_data == "JVBERi0xLjQ="
    assert request.file_url is None


def test_extract_request_allows_default_schema_registry():
    request = ExtractRequest(
        file_url="https://example.com/claim.pdf",
        documents=[_classified_document()],
    )

    assert request.extraction_schemas is None


def test_extract_request_requires_classified_documents():
    with pytest.raises(ValidationError):
        ExtractRequest(file_url="https://example.com/claim.pdf")


def test_extract_full_request_does_not_require_classified_documents():
    request = ExtractFullRequest(file_url="https://example.com/claim.pdf")

    assert request.file_url == "https://example.com/claim.pdf"
    assert request.extraction_schemas is None


def test_classify_request_accepts_document_selectors():
    request = ClassifySegmentRequest(
        file_url="https://example.com/claim.pdf",
        document_codes=[" medical_report ", "medical_report"],
        document_names=[" Báo cáo y tế "],
    )

    assert request.document_codes == ["medical_report"]
    assert request.document_names == ["báo cáo y tế"]


@pytest.mark.parametrize(
    "payload",
    [
        {"extraction_schemas": [_minimal_schema()]},
        {
            "file_url": "https://example.com/claim.pdf",
            "file_data": "JVBERi0xLjQ=",
            "documents": [_classified_document()],
            "extraction_schemas": [_minimal_schema()],
        },
    ],
)
def test_extract_request_requires_exactly_one_file_source(payload):
    with pytest.raises(ValidationError):
        ExtractRequest(**payload)


def test_default_schema_registry_loads_defined_documents():
    schemas = load_default_extraction_schemas()

    assert len(schemas) >= 20
    assert any(schema.document_code == "medical_report" for schema in schemas)


def test_default_schema_registry_resolves_by_code_name_and_dedupes():
    schemas = resolve_default_extraction_schemas(
        document_codes=["medical_report", "medical_report"],
        document_names=["Báo cáo y tế"],
    )

    assert [schema.document_code for schema in schemas] == ["medical_report"]


def test_default_schema_registry_rejects_unknown_selector():
    with pytest.raises(SchemaSelectionError):
        resolve_default_extraction_schemas(document_codes=["not_a_known_doc"])


def test_default_schema_registry_converts_to_classification_schemas():
    schemas = resolve_default_extraction_schemas(document_codes=["medical_report"])
    classification_schemas = to_classification_schemas(schemas)

    assert classification_schemas[0].document_code == "medical_report"
    assert classification_schemas[0].document_name == schemas[0].document_name
