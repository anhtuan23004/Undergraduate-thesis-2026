from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from app.config import settings
from core.ocr_engine import GeminiOCRService, GeminiConfigError
from core.utils import download_file_from_url
from utils.logging import get_logger

logger = get_logger(__name__)

# Health check router
health_router = APIRouter()

@health_router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Service status, name, and version.
    """
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": settings.VERSION}


# OCR router
ocr_router = APIRouter(prefix=f"{settings.API_PREFIX}/ocr", tags=["ocr"])

def get_ocr_service(api_key: Optional[str] = Form(None)) -> GeminiOCRService:
    """
    Dependency to get OCR service instance.
    
    Args:
        api_key: Optional API key override.
        
    Returns:
        GeminiOCRService instance.
        
    Raises:
        HTTPException: If configuration is invalid.
    """
    try:
        return GeminiOCRService(api_key=api_key)
    except GeminiConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
):
    """
    Raw text extraction from images/PDFs.
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
        thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
        thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
        service: OCR service instance.
        
    Returns:
        dict: Extracted raw text.
    """
    if not file and not file_url:
        logger.warning("ocr_raw request missing both file and file_url")
        raise HTTPException(status_code=400, detail="Either 'file' or 'file_url' must be provided.")

    try:
        if file:
            if not file.content_type:
                 raise HTTPException(status_code=400, detail="File must have a content type")
            file_bytes = await file.read()
            file_name_val = file.filename or "uploaded_file"
            mime_type = file.content_type
            logger.info(f"Processing upload file: {file_name_val} ({mime_type})")
        else:
            logger.info(f"Downloading file from URL: {file_url}")
            file_bytes, file_name_val, mime_type = await download_file_from_url(file_url) # type: ignore

        result = service.parse_raw(
            file_bytes=file_bytes,
            file_name=file_name_val,
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
        return result
        # return {"raw_text": result}
    except GeminiConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in ocr_raw: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
):
    """
    Structured field extraction (JSON format) from images/PDFs.
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
        thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
        thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
        service: OCR service instance.
        
    Returns:
        dict: Extracted fields.
    """
    if not file and not file_url:
         logger.warning("ocr_fields request missing both file and file_url")
         raise HTTPException(status_code=400, detail="Either 'file' or 'file_url' must be provided.")

    try:
        if file:
            if not file.content_type:
                raise HTTPException(status_code=400, detail="File must have a content type")
            file_bytes = await file.read()
            file_name_val = file.filename or "uploaded_file"
            mime_type = file.content_type
            logger.info(f"Processing upload file: {file_name_val} ({mime_type})")
        else:
            logger.info(f"Downloading file from URL: {file_url}")
            file_bytes, file_name_val, mime_type = await download_file_from_url(file_url) # type: ignore

        result = service.parse_fields(
            file_bytes=file_bytes,
            file_name=file_name_val,
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
        return result
        # return {"extracted_fields": result}
    except GeminiConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in ocr_fields: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
):
    """
    Document structure extraction (JSON format) from images/PDFs.
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
        thinking_budget: Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget).
        thinking_level: Thinking level for Gemini 3 (minimal/low/medium/high).
        service: OCR service instance.

    Returns:
        dict: Extracted document structure.
    """
    if not file and not file_url:
         logger.warning("ocr_document request missing both file and file_url")
         raise HTTPException(status_code=400, detail="Either 'file' or 'file_url' must be provided.")

    try:
        if file:
            if not file.content_type:
                raise HTTPException(status_code=400, detail="File must have a content type")
            file_bytes = await file.read()
            file_name_val = file.filename or "uploaded_file"
            mime_type = file.content_type
            logger.info(f"Processing upload file: {file_name_val} ({mime_type})")
        else:
            logger.info(f"Downloading file from URL: {file_url}")
            file_bytes, file_name_val, mime_type = await download_file_from_url(file_url) # type: ignore

        result = service.parse_document(
            file_bytes=file_bytes,
            file_name=file_name_val,
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
        return result
    except GeminiConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in ocr_document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
