"""API routes for the OCR service."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import settings
from core.ocr_engine import GeminiConfigError, GeminiOCRService
from core.utils import download_file_from_url
from utils.logging import get_logger

logger = get_logger(__name__)

# Router definitions
health_router = APIRouter()
ocr_router = APIRouter(prefix=f"{settings.API_PREFIX}/ocr", tags=["ocr"])

# Common OCR parameters type alias
OCRParams = dict[str, Any]


def get_ocr_service(api_key: Optional[str] = Form(None)) -> GeminiOCRService:
    """Dependency to get OCR service instance.

    Args:
        api_key: Optional API key override.

    Returns:
        GeminiOCRService instance.

    Raises:
        HTTPException: If configuration is invalid.
    """
    try:
        return GeminiOCRService(api_key=api_key)
    except GeminiConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_file_content(
    file: Optional[UploadFile],
    file_url: Optional[str],
    operation: str,
) -> tuple[bytes, str, str]:
    """Get file content from upload or URL.

    Args:
        file: Uploaded file (optional).
        file_url: URL to download file from (optional).
        operation: Name of the operation for logging.

    Returns:
        Tuple of (file bytes, filename, MIME type).

    Raises:
        HTTPException: If neither file nor URL is provided, or validation fails.
    """
    if not file and not file_url:
        logger.warning(f"{operation} request missing both file and file_url")
        raise HTTPException(
            status_code=400,
            detail="Either 'file' or 'file_url' must be provided.",
        )

    if file:
        if not file.content_type:
            raise HTTPException(status_code=400, detail="File must have a content type")

        file_bytes = await file.read()
        file_name = file.filename or "uploaded_file"
        mime_type = file.content_type
        logger.info(f"Processing upload file: {file_name} ({mime_type})")
        return file_bytes, file_name, mime_type

    # Download from URL
    logger.info(f"Downloading file from URL: {file_url}")
    return await download_file_from_url(file_url)


def handle_ocr_error(operation: str, exc: Exception) -> None:
    """Handle OCR errors consistently.

    Args:
        operation: Name of the operation.
        exc: The exception that occurred.

    Raises:
        HTTPException: With appropriate status code and detail.
    """
    if isinstance(exc, GeminiConfigError):
        logger.error(f"Configuration error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.error(f"Unexpected error in {operation}: {exc}", exc_info=True)
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@health_router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Service status information.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@ocr_router.post("/raw")
async def ocr_raw(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    temperature: Optional[float] = Form(None),
    top_p: Optional[float] = Form(None),
    top_k: Optional[int] = Form(None),
    max_output_tokens: Optional[int] = Form(None),
    thinking_budget: Optional[int] = Form(None),
    thinking_level: Optional[str] = Form(None),
    service: GeminiOCRService = Depends(get_ocr_service),
) -> str:
    """Extract raw text from images/PDFs.

    Provide either 'file' (upload) or 'file_url'.

    Args:
        file: Uploaded file.
        file_url: URL to download file from.
        prompt: Optional custom prompt.
        model_name: Optional model override.
        temperature: Controls randomness (0.0-2.0).
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum tokens to generate.
        thinking_budget: Token budget for Gemini 2.5.
        thinking_level: Thinking level for Gemini 3.
        service: OCR service instance (injected).

    Returns:
        Extracted raw text.
    """
    try:
        file_bytes, file_name, mime_type = await get_file_content(
            file, file_url, "ocr_raw"
        )

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
    except Exception as exc:
        handle_ocr_error("ocr_raw", exc)


@ocr_router.post("/fields")
async def ocr_fields(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    temperature: Optional[float] = Form(None),
    top_p: Optional[float] = Form(None),
    top_k: Optional[int] = Form(None),
    max_output_tokens: Optional[int] = Form(None),
    thinking_budget: Optional[int] = Form(None),
    thinking_level: Optional[str] = Form(None),
    service: GeminiOCRService = Depends(get_ocr_service),
) -> Any:
    """Extract structured fields (JSON format) from images/PDFs.

    Provide either 'file' (upload) or 'file_url'.

    Args:
        file: Uploaded file.
        file_url: URL to download file from.
        prompt: Optional custom prompt.
        model_name: Optional model override.
        temperature: Controls randomness (0.0-2.0).
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum tokens to generate.
        thinking_budget: Token budget for Gemini 2.5.
        thinking_level: Thinking level for Gemini 3.
        service: OCR service instance (injected).

    Returns:
        Extracted fields as JSON.
    """
    try:
        file_bytes, file_name, mime_type = await get_file_content(
            file, file_url, "ocr_fields"
        )

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
    except Exception as exc:
        handle_ocr_error("ocr_fields", exc)


@ocr_router.post("/document")
async def ocr_document(
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    temperature: Optional[float] = Form(None),
    top_p: Optional[float] = Form(None),
    top_k: Optional[int] = Form(None),
    max_output_tokens: Optional[int] = Form(None),
    thinking_budget: Optional[int] = Form(None),
    thinking_level: Optional[str] = Form(None),
    service: GeminiOCRService = Depends(get_ocr_service),
) -> Any:
    """Extract document structure (JSON format) from images/PDFs.

    Provide either 'file' (upload) or 'file_url'.

    Args:
        file: Uploaded file.
        file_url: URL to download file from.
        prompt: Optional custom prompt.
        model_name: Optional model override.
        temperature: Controls randomness (0.0-2.0).
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum tokens to generate.
        thinking_budget: Token budget for Gemini 2.5.
        thinking_level: Thinking level for Gemini 3.
        service: OCR service instance (injected).

    Returns:
        Extracted document structure as JSON.
    """
    try:
        file_bytes, file_name, mime_type = await get_file_content(
            file, file_url, "ocr_document"
        )

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
    except Exception as exc:
        handle_ocr_error("ocr_document", exc)
