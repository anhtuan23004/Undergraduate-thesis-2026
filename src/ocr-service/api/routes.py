"""FastAPI route definitions for the OCR service."""

from typing import Any

from core.config import settings
from core.engine.v1 import OCRServiceV1
from core.engine.v2 import OCRServiceV2
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
    SchemaSelectionError,
    resolve_default_extraction_schemas,
    to_classification_schemas,
)

from api.utils import (
    get_file_content,
    handle_ocr_error,
    parse_json_list,
    parse_model_list,
    parse_schema_list,
    validate_model_response,
)

health_router = APIRouter()
ocr_router_v1 = APIRouter(prefix=f"{settings.API_PREFIX}/ocr", tags=["ocr-v1"])
ocr_router_v2 = APIRouter(prefix=f"{settings.API_V2_PREFIX}/ocr", tags=["ocr-v2"])
ocr_router_v2_form = APIRouter(prefix=f"{settings.API_V2_PREFIX}/ocr", tags=["ocr-v2-form"])


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


def _resolve_v2_extraction_schemas(
    *,
    extraction_schemas: list[ExtractionSchema] | None = None,
    document_codes: list[str] | None = None,
    document_names: list[str] | None = None,
) -> list[ExtractionSchema]:
    if extraction_schemas:
        return extraction_schemas

    try:
        return resolve_default_extraction_schemas(
            document_codes=document_codes,
            document_names=document_names,
        )
    except SchemaSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _resolve_v2_classification_schemas(
    *,
    extraction_schemas: list[ClassificationSchema] | None = None,
    document_codes: list[str] | None = None,
    document_names: list[str] | None = None,
) -> list[ClassificationSchema]:
    if extraction_schemas:
        return extraction_schemas

    schemas = _resolve_v2_extraction_schemas(
        document_codes=document_codes,
        document_names=document_names,
    )
    return to_classification_schemas(schemas)


async def _get_v2_file_content_from_request(
    request: PrefilterRequest | ClassifySegmentRequest | ExtractRequest | ExtractFullRequest,
    operation: str,
) -> tuple[bytes, str, str]:
    return await get_file_content(
        file_url=request.file_url,
        file_data=request.file_data,
        operation=operation,
    )


def _parse_optional_string_list(raw: str | None, field_name: str) -> list[str] | None:
    if not raw:
        return None

    values = parse_json_list(raw, field_name)
    if not all(isinstance(value, str) for value in values):
        raise HTTPException(status_code=422, detail=f"{field_name} must contain only strings")
    return values


def _run_v2_classify_segment(
    *,
    service: OCRServiceV2,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    extraction_schemas: list[ClassificationSchema],
    model_name: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_output_tokens: int | None = None,
    thinking_budget: int | None = None,
    thinking_level: str | None = None,
    log_prefix: str,
) -> ClassifySegmentResponse:
    result = service.run_classify_and_segment(
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=mime_type,
        extraction_schemas=extraction_schemas,
        extract_all_documents=settings.OCR_EXTRACT_ALL_DOCUMENTS,
        model_name=model_name,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
    )
    return validate_model_response(
        result=result,
        response_model=ClassifySegmentResponse.model_validate,
        log_prefix=log_prefix,
    )


def _run_v2_extract(
    *,
    service: OCRServiceV2,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    documents: list[ClassifySegmentDocument],
    extraction_schemas: list[ExtractionSchema],
    extract_all_fields: bool = False,
    model_name: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_output_tokens: int | None = None,
    thinking_budget: int | None = None,
    thinking_level: str | None = None,
    log_prefix: str,
) -> ExtractResponse:
    result = service.extract_classified_documents(
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=mime_type,
        documents=documents,
        extraction_schemas=extraction_schemas,
        extract_all_fields=extract_all_fields,
        model_name=model_name,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
    )
    return validate_model_response(
        result=result,
        response_model=ExtractResponse.model_validate,
        log_prefix=log_prefix,
    )


def _run_v2_extract_full(
    *,
    service: OCRServiceV2,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    extraction_schemas: list[ExtractionSchema],
    extract_all_fields: bool = False,
    model_name: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_output_tokens: int | None = None,
    thinking_budget: int | None = None,
    thinking_level: str | None = None,
    log_prefix: str,
) -> ExtractResponse:
    classification = _run_v2_classify_segment(
        service=service,
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=mime_type,
        extraction_schemas=to_classification_schemas(extraction_schemas),
        model_name=model_name,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
        log_prefix=log_prefix,
    )
    return _run_v2_extract(
        service=service,
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=mime_type,
        documents=classification.documents,
        extraction_schemas=extraction_schemas,
        extract_all_fields=extract_all_fields,
        model_name=model_name,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
        log_prefix=log_prefix,
    )


@ocr_router_v2.post(
    "/prefilter", response_model=PrefilterResponse, response_model_exclude_none=True
)
async def ocr_prefilter_v2(request: PrefilterRequest) -> PrefilterResponse:
    """Run v2 prefilter to check if a document is in scope."""
    async with handle_ocr_error("ocr_prefilter_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await _get_v2_file_content_from_request(
            request, "v2_json"
        )
        result = service.run_prefilter_only(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            model_name=request.model_name,
        )
        return PrefilterResponse.model_validate(result)


@ocr_router_v2.post(
    "/classify-segment", response_model=ClassifySegmentResponse, response_model_exclude_none=True
)
async def ocr_classify_segment_v2(request: ClassifySegmentRequest) -> ClassifySegmentResponse:
    """Run v2 phase 1 classification and segmentation."""
    async with handle_ocr_error("ocr_classify_segment_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await _get_v2_file_content_from_request(
            request, "v2_json"
        )
        extraction_schemas = _resolve_v2_classification_schemas(
            extraction_schemas=request.extraction_schemas,
            document_codes=request.document_codes,
            document_names=request.document_names,
        )
        return _run_v2_classify_segment(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas,
            model_name=request.model_name,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_output_tokens=request.max_output_tokens,
            thinking_budget=request.thinking_budget,
            thinking_level=request.thinking_level,
            log_prefix="V2",
        )


@ocr_router_v2.post("/extract", response_model=ExtractResponse, response_model_exclude_none=True)
async def ocr_extract_v2(request: ExtractRequest) -> ExtractResponse:
    """Run v2 schema-driven multi-document extraction."""
    async with handle_ocr_error("ocr_extract_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await _get_v2_file_content_from_request(
            request, "v2_json"
        )
        extraction_schemas = _resolve_v2_extraction_schemas(
            extraction_schemas=request.extraction_schemas,
            document_codes=request.document_codes,
            document_names=request.document_names,
        )
        return _run_v2_extract(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            documents=request.documents,
            extraction_schemas=extraction_schemas,
            extract_all_fields=request.extract_all_fields,
            model_name=request.model_name,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_output_tokens=request.max_output_tokens,
            thinking_budget=request.thinking_budget,
            thinking_level=request.thinking_level,
            log_prefix="V2",
        )


@ocr_router_v2.post(
    "/extract-full", response_model=ExtractResponse, response_model_exclude_none=True
)
async def ocr_extract_full_v2(request: ExtractFullRequest) -> ExtractResponse:
    """Run v2 full classify-then-extract pipeline."""
    async with handle_ocr_error("ocr_extract_full_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await _get_v2_file_content_from_request(
            request, "v2_json"
        )
        extraction_schemas = _resolve_v2_extraction_schemas(
            extraction_schemas=request.extraction_schemas,
            document_codes=request.document_codes,
            document_names=request.document_names,
        )
        return _run_v2_extract_full(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas,
            extract_all_fields=request.extract_all_fields,
            model_name=request.model_name,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_output_tokens=request.max_output_tokens,
            thinking_budget=request.thinking_budget,
            thinking_level=request.thinking_level,
            log_prefix="V2 Full",
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
        resolved_schemas = _resolve_v2_extraction_schemas(
            extraction_schemas=extraction_schemas_obj,
            document_codes=_parse_optional_string_list(document_codes, "document_codes"),
            document_names=_parse_optional_string_list(document_names, "document_names"),
        )
        documents_obj = parse_model_list(
            documents,
            "documents",
            ClassifySegmentDocument.model_validate,
        )
        service = OCRServiceV2(api_key=api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file=file,
            file_url=file_url,
            file_data=file_data,
            operation="v2_form",
        )
        return _run_v2_extract(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            documents=documents_obj,
            extraction_schemas=resolved_schemas,
            extract_all_fields=extract_all_fields,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            log_prefix="V2 Form",
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
        resolved_schemas = _resolve_v2_classification_schemas(
            extraction_schemas=extraction_schemas_obj,
            document_codes=_parse_optional_string_list(document_codes, "document_codes"),
            document_names=_parse_optional_string_list(document_names, "document_names"),
        )

        service = OCRServiceV2(api_key=api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file=file,
            file_url=file_url,
            file_data=file_data,
            operation="v2_form",
        )
        return _run_v2_classify_segment(
            service=service,
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=resolved_schemas,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            log_prefix="V2 Form",
        )
