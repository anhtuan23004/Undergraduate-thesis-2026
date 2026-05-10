"""Shared API helpers for OCR route handlers."""

import base64
import binascii
import json
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from core.engine.base import GeminiConfigError
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from utils.gemini import (
    download_file_from_url,
    sanitize_filename,
    validate_file_size,
    validate_mime_type,
)
from utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def handle_ocr_error(endpoint_name: str) -> AsyncGenerator[None, None]:
    """Convert OCR engine exceptions into HTTP responses."""
    try:
        yield
    except HTTPException:
        raise
    except GeminiConfigError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in {endpoint_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


async def get_file_content(  # noqa: C901
    file: UploadFile | None = None,
    file_url: str | None = None,
    file_data: str | None = None,
    operation: str = "ocr",
) -> tuple[bytes, str, str]:
    """Resolve file bytes from exactly one upload, URL, or base64 source."""
    provided = sum(bool(x) for x in (file, file_url, file_data))
    if provided != 1:
        logger.warning(
            f"{operation} request must provide exactly one of: file, file_url, or file_data."
        )
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one source: 'file', 'file_url', or 'file_data'.",
        )

    if file:
        return await _read_upload_file(file)
    if file_data:
        return _read_base64_file(file_data)

    logger.info(f"Downloading file from URL: {file_url}")
    return await download_file_from_url(file_url)


def validate_model_response(
    *,
    result: Any,
    response_model: Callable[[Any], Any],
    log_prefix: str,
) -> Any:
    """Validate a Gemini result against an API response model."""
    if not isinstance(result, dict):
        logger.error(f"[{log_prefix}] Unexpected response type from model: {type(result)}")
        raise HTTPException(
            status_code=502,
            detail="Model returned an unexpected response structure. Please retry.",
        )

    try:
        return response_model(result)
    except ValidationError as e:
        logger.error(f"[{log_prefix}] Invalid response payload from model: {e}")
        raise HTTPException(
            status_code=502,
            detail="Model returned an invalid response payload. Please retry.",
        ) from e


def parse_schema_list(raw: str, schema_model: Callable[[Any], Any]) -> list[Any]:
    """Parse a JSON form field into a list of schema models."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="extraction_schemas must be valid JSON",
        ) from None

    if not isinstance(payload, list):
        raise HTTPException(
            status_code=400,
            detail="extraction_schemas must be a JSON array",
        )

    try:
        return [schema_model(item) for item in payload]
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e


async def _read_upload_file(file: UploadFile) -> tuple[bytes, str, str]:
    if not file.content_type:
        raise HTTPException(status_code=400, detail="File must have a content type")

    mime_type = file.content_type.split(";")[0].strip().lower()
    validate_mime_type(mime_type)
    file_bytes = await file.read()
    validate_file_size(None, len(file_bytes))

    file_name = sanitize_filename(file.filename or "uploaded_file")
    logger.info(f"Processing upload file: {file_name} ({mime_type})")
    return file_bytes, file_name, mime_type


def _read_base64_file(file_data: str) -> tuple[bytes, str, str]:
    try:
        encoded, mime_type = _split_base64_payload(file_data)
        file_bytes = base64.b64decode(encoded)
        validate_file_size(None, len(file_bytes))

        if mime_type == "application/octet-stream":
            mime_type = _detect_mime_from_magic_bytes(file_bytes)

        mime_type = mime_type.split(";")[0].strip().lower()
        validate_mime_type(mime_type)
        logger.info(f"Processing base64 file data ({mime_type})")
        return file_bytes, "base64_upload", mime_type
    except HTTPException:
        raise
    except (ValueError, binascii.Error) as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {e}") from e


def _split_base64_payload(file_data: str) -> tuple[str, str]:
    if file_data.startswith("data:"):
        header, encoded = file_data.split(",", 1)
        return encoded, header.split(":")[1].split(";")[0]
    return file_data, "application/octet-stream"


def _detect_mime_from_magic_bytes(file_bytes: bytes) -> str:
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    return "application/octet-stream"
