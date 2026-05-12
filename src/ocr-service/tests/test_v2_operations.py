"""Operation-level tests for OCR service v2."""

import pytest
from api.v2_operations import (
    OCRV2Operations,
    V2ClassifySegmentCommand,
    V2ExtractFullCommand,
    V2FileSource,
    V2ModelOptions,
    V2PrefilterCommand,
)
from fastapi import HTTPException


class FakeOCRServiceV2:
    last_instance = None

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.classify_kwargs = None
        self.extract_kwargs = None
        self.prefilter_kwargs = None
        FakeOCRServiceV2.last_instance = self

    def run_prefilter_only(self, **kwargs):
        self.prefilter_kwargs = kwargs
        return {"is_valid_document": True}

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


class InvalidPrefilterOCRServiceV2(FakeOCRServiceV2):
    def run_prefilter_only(self, **kwargs):
        self.prefilter_kwargs = kwargs
        return {"unexpected": True}


async def fake_file_loader(**kwargs):
    return b"%PDF-1.4", "claim.pdf", "application/pdf"


@pytest.mark.asyncio
async def test_classify_operation_resolves_selectors_and_model_options():
    operations = OCRV2Operations(
        engine_factory=FakeOCRServiceV2,
        file_loader=fake_file_loader,
    )

    response = await operations.classify_segment(
        V2ClassifySegmentCommand(
            source=V2FileSource(file_url="https://example.com/claim.pdf"),
            document_codes=["medical_report"],
            model_options=V2ModelOptions(model_name="gemini-test", temperature=0.2),
            api_key="secret",
        )
    )

    service = FakeOCRServiceV2.last_instance
    assert service.api_key == "secret"
    assert service.classify_kwargs["file_bytes"] == b"%PDF-1.4"
    assert service.classify_kwargs["model_name"] == "gemini-test"
    assert service.classify_kwargs["temperature"] == 0.2
    assert [schema.document_code for schema in service.classify_kwargs["extraction_schemas"]] == [
        "medical_report"
    ]
    assert response.documents[0].document_code == "unknown"


@pytest.mark.asyncio
async def test_extract_full_operation_runs_classify_then_extract_on_one_engine():
    operations = OCRV2Operations(
        engine_factory=FakeOCRServiceV2,
        file_loader=fake_file_loader,
    )

    response = await operations.extract_full(
        V2ExtractFullCommand(
            source=V2FileSource(file_data="JVBERi0xLjQ="),
            document_codes=["medical_report"],
        )
    )

    service = FakeOCRServiceV2.last_instance
    assert service.classify_kwargs is not None
    assert service.extract_kwargs is not None
    assert service.extract_kwargs["documents"][0].document_code == "unknown"
    assert [schema.document_code for schema in service.extract_kwargs["extraction_schemas"]] == [
        "medical_report"
    ]
    assert response.documents[0].extracted_data == {}


@pytest.mark.asyncio
async def test_prefilter_operation_validates_engine_payload():
    operations = OCRV2Operations(
        engine_factory=InvalidPrefilterOCRServiceV2,
        file_loader=fake_file_loader,
    )

    with pytest.raises(HTTPException) as exc_info:
        await operations.prefilter(
            V2PrefilterCommand(
                source=V2FileSource(file_url="https://example.com/claim.pdf"),
            )
        )

    assert exc_info.value.status_code == 502
