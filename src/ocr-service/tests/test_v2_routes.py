"""Route-level tests for OCR v2 schema selection behavior."""

import api.routes as routes
import pytest
from schemas import ClassifySegmentRequest, ExtractFullRequest, ExtractRequest


class FakeOCRServiceV2:
    last_instance = None

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.classify_kwargs = None
        self.extract_kwargs = None
        FakeOCRServiceV2.last_instance = self

    def run_classify_and_segment(self, **kwargs):
        self.classify_kwargs = kwargs
        return {
            "documents": [
                {
                    "document_code": "unknown",
                    "document_name": "",
                    "suggested_document_code": "other_document",
                    "suggested_document_name": "Chứng từ khác",
                    "start_page": 1,
                    "end_page": 1,
                }
            ]
        }

    def extract_classified_documents(self, **kwargs):
        self.extract_kwargs = kwargs
        return {
            "documents": [
                {
                    "document_code": "unknown",
                    "document_name": "",
                    "suggested_document_code": "other_document",
                    "suggested_document_name": "Chứng từ khác",
                    "start_page": 1,
                    "end_page": 1,
                    "extracted_data": {},
                }
            ]
        }


async def fake_file_content_from_request(request, operation):
    return b"%PDF-1.4", "claim.pdf", "application/pdf"


@pytest.fixture
def fake_v2_service(monkeypatch):
    monkeypatch.setattr(routes, "OCRServiceV2", FakeOCRServiceV2)
    monkeypatch.setattr(routes, "_get_v2_file_content_from_request", fake_file_content_from_request)
    return FakeOCRServiceV2


@pytest.mark.asyncio
async def test_classify_selector_still_allows_unknown(fake_v2_service):
    response = await routes.ocr_classify_segment_v2(
        ClassifySegmentRequest(
            file_url="https://example.com/claim.pdf",
            document_codes=["medical_report"],
        )
    )

    kwargs = fake_v2_service.last_instance.classify_kwargs
    assert kwargs["extract_all_documents"] is True
    assert [schema.document_code for schema in kwargs["extraction_schemas"]] == ["medical_report"]
    assert response.documents[0].document_code == "unknown"
    assert response.documents[0].suggested_document_code == "other_document"


@pytest.mark.asyncio
async def test_classify_uses_extract_all_documents_config(fake_v2_service, monkeypatch):
    monkeypatch.setattr(routes.settings, "OCR_EXTRACT_ALL_DOCUMENTS", False)

    await routes.ocr_classify_segment_v2(
        ClassifySegmentRequest(
            file_url="https://example.com/claim.pdf",
            document_codes=["medical_report"],
        )
    )

    kwargs = fake_v2_service.last_instance.classify_kwargs
    assert kwargs["extract_all_documents"] is False


@pytest.mark.asyncio
async def test_classify_without_selector_uses_default_registry(fake_v2_service):
    await routes.ocr_classify_segment_v2(
        ClassifySegmentRequest(file_url="https://example.com/claim.pdf")
    )

    kwargs = fake_v2_service.last_instance.classify_kwargs
    assert kwargs["extract_all_documents"] is True
    assert len(kwargs["extraction_schemas"]) >= 20


@pytest.mark.asyncio
async def test_extract_without_schema_uses_default_registry_and_unknown(fake_v2_service):
    response = await routes.ocr_extract_v2(
        ExtractRequest(
            file_url="https://example.com/claim.pdf",
            documents=[
                {
                    "document_code": "unknown",
                    "document_name": "",
                    "start_page": 1,
                    "end_page": 1,
                }
            ],
        )
    )

    kwargs = fake_v2_service.last_instance.extract_kwargs
    assert len(kwargs["documents"]) == 1
    assert len(kwargs["extraction_schemas"]) >= 20
    assert response.documents[0].document_code == "unknown"


@pytest.mark.asyncio
async def test_extract_does_not_run_classify(fake_v2_service):
    await routes.ocr_extract_v2(
        ExtractRequest(
            file_url="https://example.com/claim.pdf",
            documents=[
                {
                    "document_code": "medical_report",
                    "document_name": "Báo cáo y tế",
                    "start_page": 1,
                    "end_page": 1,
                }
            ],
        )
    )

    assert fake_v2_service.last_instance.classify_kwargs is None


@pytest.mark.asyncio
async def test_extract_full_runs_classify_then_extract(fake_v2_service):
    response = await routes.ocr_extract_full_v2(
        ExtractFullRequest(
            file_url="https://example.com/claim.pdf",
            document_codes=["medical_report"],
        )
    )

    service = fake_v2_service.last_instance
    assert service.classify_kwargs["extract_all_documents"] is True
    assert [schema.document_code for schema in service.classify_kwargs["extraction_schemas"]] == [
        "medical_report"
    ]
    assert len(service.extract_kwargs["documents"]) == 1
    assert service.extract_kwargs["documents"][0].document_code == "unknown"
    assert [schema.document_code for schema in service.extract_kwargs["extraction_schemas"]] == [
        "medical_report"
    ]
    assert response.documents[0].document_code == "unknown"


@pytest.mark.asyncio
async def test_extract_explicit_schema_takes_precedence(fake_v2_service):
    await routes.ocr_extract_v2(
        ExtractRequest(
            file_url="https://example.com/claim.pdf",
            documents=[
                {
                    "document_code": "custom_doc",
                    "document_name": "Custom",
                    "start_page": 1,
                    "end_page": 1,
                }
            ],
            document_codes=["medical_report"],
            extraction_schemas=[
                {
                    "document_code": "custom_doc",
                    "document_name": "Custom",
                    "fields": [{"field_key": "custom_field", "data_type": "string"}],
                }
            ],
        )
    )

    kwargs = fake_v2_service.last_instance.extract_kwargs
    assert [schema.document_code for schema in kwargs["extraction_schemas"]] == ["custom_doc"]
