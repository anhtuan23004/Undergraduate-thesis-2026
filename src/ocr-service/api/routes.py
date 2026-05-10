"""FastAPI route definitions for the OCR service."""

from core.config import settings
from core.engine.v1 import OCRServiceV1
from core.engine.v2 import OCRServiceV2
from fastapi import APIRouter, Depends, File, Form, UploadFile
from schemas import (
    ClassificationSchema,
    ClassifySegmentRequest,
    ClassifySegmentResponse,
    ExtractionSchema,
    ExtractRequest,
    ExtractResponse,
    PrefilterRequest,
    PrefilterResponse,
)
from utils.logging import get_logger

from api.utils import (
    get_file_content,
    handle_ocr_error,
    parse_schema_list,
    validate_model_response,
)

logger = get_logger(__name__)

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
):
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
):
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
):
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


@ocr_router_v2.post(
    "/prefilter", response_model=PrefilterResponse, response_model_exclude_none=True
)
async def ocr_prefilter_v2(request: PrefilterRequest):
    """Run v2 prefilter to check if a document is in scope."""
    async with handle_ocr_error("ocr_prefilter_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file_url=request.file_url,
            file_data=request.file_data,
            operation="v2_json",
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
async def ocr_classify_segment_v2(request: ClassifySegmentRequest):
    """Run v2 phase 1 classification and segmentation."""
    async with handle_ocr_error("ocr_classify_segment_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file_url=request.file_url,
            file_data=request.file_data,
            operation="v2_json",
        )

        result = service.run_classify_and_segment(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=request.extraction_schemas,
            extract_all_documents=request.extract_all_documents,
            model_name=request.model_name,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_output_tokens=request.max_output_tokens,
            thinking_budget=request.thinking_budget,
            thinking_level=request.thinking_level,
        )
        return validate_model_response(
            result=result,
            response_model=ClassifySegmentResponse.model_validate,
            log_prefix="V2",
        )


@ocr_router_v2.post("/extract", response_model=ExtractResponse, response_model_exclude_none=True)
async def ocr_extract_v2(request: ExtractRequest):
    """Run v2 schema-driven multi-document extraction."""
    async with handle_ocr_error("ocr_extract_v2"):
        service = OCRServiceV2(api_key=request.api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file_url=request.file_url,
            file_data=request.file_data,
            operation="v2_json",
        )

        result = service.parse_with_schema_v2(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=request.extraction_schemas,
            extract_all_fields=request.extract_all_fields,
            extract_all_documents=request.extract_all_documents,
            model_name=request.model_name,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_output_tokens=request.max_output_tokens,
            thinking_budget=request.thinking_budget,
            thinking_level=request.thinking_level,
        )
        return validate_model_response(
            result=result,
            response_model=ExtractResponse.model_validate,
            log_prefix="V2",
        )


@ocr_router_v2_form.post(
    "/extract/form", response_model=ExtractResponse, response_model_exclude_none=True
)
async def ocr_extract_v2_form(
    file: UploadFile | None = File(None),
    file_url: str | None = Form(None),
    file_data: str | None = Form(None),
    extraction_schemas: str = Form(...),
    extract_all_fields: bool = Form(False),
    extract_all_documents: bool = Form(False),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    api_key: str | None = Form(None),
):
    """Run v2 schema-driven extraction from multipart/form input."""
    async with handle_ocr_error("ocr_extract_v2_form"):
        extraction_schemas_obj = parse_schema_list(
            extraction_schemas,
            ExtractionSchema.model_validate,
        )
        service = OCRServiceV2(api_key=api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file=file,
            file_url=file_url,
            file_data=file_data,
            operation="v2_form",
        )

        result = service.parse_with_schema_v2(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas_obj,
            extract_all_fields=extract_all_fields,
            extract_all_documents=extract_all_documents,
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
    extract_all_documents: bool = Form(False),
    model_name: str | None = Form(None),
    temperature: float | None = Form(None),
    top_p: float | None = Form(None),
    top_k: int | None = Form(None),
    max_output_tokens: int | None = Form(None),
    thinking_budget: int | None = Form(None),
    thinking_level: str | None = Form(None),
    api_key: str | None = Form(None),
):
    """Run v2 classification and segmentation from multipart/form input."""
    async with handle_ocr_error("ocr_classify_segment_v2_form"):
        extraction_schemas_obj = None
        if extraction_schemas:
            extraction_schemas_obj = parse_schema_list(
                extraction_schemas,
                ClassificationSchema.model_validate,
            )

        service = OCRServiceV2(api_key=api_key)
        file_bytes, file_name, mime_type = await get_file_content(
            file=file,
            file_url=file_url,
            file_data=file_data,
            operation="v2_form",
        )

        result = service.run_classify_and_segment(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas_obj,
            extract_all_documents=extract_all_documents,
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
            log_prefix="V2 Form",
        )
