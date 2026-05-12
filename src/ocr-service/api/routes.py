"""FastAPI route definitions for the OCR service."""

from typing import Any

from core.config import settings
from core.engine.v1 import OCRServiceV1
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from schemas import (
    ClassificationSchema,
    ClassifySegmentDocument,
    ClassifySegmentRequest,
    ClassifySegmentResponse,
    ExtractFullRequest,
    ExtractionSchema,
    ExtractRequest,
    ExtractResponse,
    PrefilterRequest,
    PrefilterResponse,
)

from api.utils import (
    get_file_content,
    handle_ocr_error,
    parse_json_list,
    parse_model_list,
    parse_schema_list,
)
from api.v2_operations import (
    OCRV2Operations,
    V2ClassifySegmentCommand,
    V2ExtractCommand,
    V2ExtractFullCommand,
    V2ModelOptions,
    V2PrefilterCommand,
    v2_form_file_source,
    v2_json_file_source,
)

health_router = APIRouter()
ocr_router_v1 = APIRouter(prefix=f"{settings.API_PREFIX}/ocr", tags=["ocr-v1"])
ocr_router_v2 = APIRouter(prefix=f"{settings.API_V2_PREFIX}/ocr", tags=["ocr-v2"])
ocr_router_v2_form = APIRouter(prefix=f"{settings.API_V2_PREFIX}/ocr", tags=["ocr-v2-form"])
OCR_V2_OPERATIONS = OCRV2Operations()


@health_router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@ocr_router_v1.post("/raw")
async def ocr_raw(
    file: UploadFile | None = File(None),
    file_url: str | None = Form(None),
    prompt: str | None = Form(None),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    service: OCRServiceV1 = Depends(OCRServiceV1),
) -> str:
    """Extract raw text from an uploaded or URL-based image/PDF."""
    async with handle_ocr_error("ocr_raw"):
        file_bytes, file_name, mime_type = await get_file_content(file, file_url)
        return service.parse_raw(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            prompt=prompt or "",
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )


@ocr_router_v1.post("/fields")
async def ocr_fields(
    file: UploadFile | None = File(None),
    file_url: str | None = Form(None),
    prompt: str | None = Form(None),
    allowedDocTypes: str | None = Form(None),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    service: OCRServiceV1 = Depends(OCRServiceV1),
) -> Any:
    """Extract structured fields from an uploaded or URL-based image/PDF."""
    async with handle_ocr_error("ocr_fields"):
        file_bytes, file_name, mime_type = await get_file_content(file, file_url)
        return service.parse_fields(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            prompt=prompt or "",
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )


@ocr_router_v1.post("/document")
async def ocr_document(
    file: UploadFile | None = File(None),
    file_url: str | None = Form(None),
    prompt: str | None = Form(None),
    allowedDocTypes: str | None = Form(None),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    service: OCRServiceV1 = Depends(OCRServiceV1),
) -> Any:
    """Extract document structure from an uploaded or URL-based image/PDF."""
    async with handle_ocr_error("ocr_document"):
        file_bytes, file_name, mime_type = await get_file_content(file, file_url)
        return service.parse_document(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            prompt=prompt or "",
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )


def _parse_optional_string_list(raw: str | None, field_name: str) -> list[str] | None:
    if not raw:
        return None

    values = parse_json_list(raw, field_name)
    if not all(isinstance(value, str) for value in values):
        raise HTTPException(status_code=422, detail=f"{field_name} must contain only strings")
    return values


@ocr_router_v2.post(
    "/prefilter", response_model=PrefilterResponse, response_model_exclude_none=True
)
async def ocr_prefilter_v2(request: PrefilterRequest) -> PrefilterResponse:
    """Run v2 prefilter to check if a document is in scope."""
    async with handle_ocr_error("ocr_prefilter_v2"):
        return await OCR_V2_OPERATIONS.prefilter(
            V2PrefilterCommand(
                source=v2_json_file_source(request),
                api_key=request.api_key,
                model_name=request.model_name,
            )
        )


@ocr_router_v2.post(
    "/classify-segment", response_model=ClassifySegmentResponse, response_model_exclude_none=True
)
async def ocr_classify_segment_v2(request: ClassifySegmentRequest) -> ClassifySegmentResponse:
    """Run v2 phase 1 classification and segmentation."""
    async with handle_ocr_error("ocr_classify_segment_v2"):
        return await OCR_V2_OPERATIONS.classify_segment(
            V2ClassifySegmentCommand(
                source=v2_json_file_source(request),
                extraction_schemas=request.extraction_schemas,
                document_codes=request.document_codes,
                document_names=request.document_names,
                model_options=V2ModelOptions.from_payload(request),
                api_key=request.api_key,
            )
        )


@ocr_router_v2.post("/extract", response_model=ExtractResponse, response_model_exclude_none=True)
async def ocr_extract_v2(request: ExtractRequest) -> ExtractResponse:
    """Run v2 schema-driven multi-document extraction."""
    async with handle_ocr_error("ocr_extract_v2"):
        return await OCR_V2_OPERATIONS.extract(
            V2ExtractCommand(
                source=v2_json_file_source(request),
                documents=request.documents,
                extraction_schemas=request.extraction_schemas,
                document_codes=request.document_codes,
                document_names=request.document_names,
                extract_all_fields=request.extract_all_fields,
                model_options=V2ModelOptions.from_payload(request),
                api_key=request.api_key,
            )
        )


@ocr_router_v2.post(
    "/extract-full", response_model=ExtractResponse, response_model_exclude_none=True
)
async def ocr_extract_full_v2(request: ExtractFullRequest) -> ExtractResponse:
    """Run v2 full classify-then-extract pipeline."""
    async with handle_ocr_error("ocr_extract_full_v2"):
        return await OCR_V2_OPERATIONS.extract_full(
            V2ExtractFullCommand(
                source=v2_json_file_source(request),
                extraction_schemas=request.extraction_schemas,
                document_codes=request.document_codes,
                document_names=request.document_names,
                extract_all_fields=request.extract_all_fields,
                model_options=V2ModelOptions.from_payload(request),
                api_key=request.api_key,
            )
        )


@ocr_router_v2_form.post(
    "/extract/form", response_model=ExtractResponse, response_model_exclude_none=True
)
async def ocr_extract_v2_form(
    file: UploadFile | None = File(None),
    file_url: str | None = Form(None),
    file_data: str | None = Form(None),
    documents: str = Form(...),
    extraction_schemas: str | None = Form(None),
    document_codes: str | None = Form(None),
    document_names: str | None = Form(None),
    extract_all_fields: bool = Form(False),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    api_key: str | None = Form(None),
) -> ExtractResponse:
    """Run v2 schema-driven extraction from multipart/form input."""
    async with handle_ocr_error("ocr_extract_v2_form"):
        extraction_schemas_obj = (
            parse_schema_list(extraction_schemas, ExtractionSchema.model_validate)
            if extraction_schemas
            else None
        )
        documents_obj = parse_model_list(
            documents,
            "documents",
            ClassifySegmentDocument.model_validate,
        )
        return await OCR_V2_OPERATIONS.extract(
            V2ExtractCommand(
                source=v2_form_file_source(
                    file=file,
                    file_url=file_url,
                    file_data=file_data,
                ),
                documents=documents_obj,
                extraction_schemas=extraction_schemas_obj,
                document_codes=_parse_optional_string_list(document_codes, "document_codes"),
                document_names=_parse_optional_string_list(document_names, "document_names"),
                extract_all_fields=extract_all_fields,
                model_options=V2ModelOptions(
                    model_name=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    max_output_tokens=max_output_tokens,
                    thinking_budget=thinking_budget,
                    thinking_level=thinking_level,
                ),
                api_key=api_key,
                log_prefix="V2 Form",
            )
        )


@ocr_router_v2_form.post(
    "/classify-segment/form",
    response_model=ClassifySegmentResponse,
    response_model_exclude_none=True,
)
async def ocr_classify_segment_v2_form(
    file: UploadFile | None = File(None),
    file_url: str | None = Form(None),
    file_data: str | None = Form(None),
    extraction_schemas: str | None = Form(None),
    document_codes: str | None = Form(None),
    document_names: str | None = Form(None),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    api_key: str | None = Form(None),
) -> ClassifySegmentResponse:
    """Run v2 classification and segmentation from multipart/form input."""
    async with handle_ocr_error("ocr_classify_segment_v2_form"):
        extraction_schemas_obj = None
        if extraction_schemas:
            extraction_schemas_obj = parse_schema_list(
                extraction_schemas,
                ClassificationSchema.model_validate,
            )
        return await OCR_V2_OPERATIONS.classify_segment(
            V2ClassifySegmentCommand(
                source=v2_form_file_source(
                    file=file,
                    file_url=file_url,
                    file_data=file_data,
                ),
                extraction_schemas=extraction_schemas_obj,
                document_codes=_parse_optional_string_list(document_codes, "document_codes"),
                document_names=_parse_optional_string_list(document_names, "document_names"),
                model_options=V2ModelOptions(
                    model_name=model_name,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    max_output_tokens=max_output_tokens,
                    thinking_budget=thinking_budget,
                    thinking_level=thinking_level,
                ),
                api_key=api_key,
                log_prefix="V2 Form",
            )
        )
