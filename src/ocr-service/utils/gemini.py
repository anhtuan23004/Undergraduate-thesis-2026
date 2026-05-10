"""Gemini and OCR input utility functions."""

import json
import mimetypes
import re
from typing import Any, Final
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from google.genai import types

from utils.logging import get_logger

logger = get_logger(__name__)

ALLOWED_MIME_TYPES: Final[set[str]] = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/pdf",
}
MAX_FILE_SIZE: Final[int] = 50 * 1024 * 1024
MAX_FILENAME_LENGTH: Final[int] = 100
MAX_EXTENSION_LENGTH: Final[int] = 10
GEMINI_3_PATTERNS: Final[tuple[str, ...]] = ("gemini-3", "gemini3", "gemini-exp-")
MARKDOWN_PATTERNS: Final[tuple[str, ...]] = (
    r"```(?:json)?\s*\n?(.*?)\n?```",
    r"`([^`]+)`",
)


def validate_url(url: str) -> None:
    """Validate URL format and scheme."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400,
                detail="Only HTTP and HTTPS URLs are allowed",
            )
        if not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail="Invalid URL format") from exc


def sanitize_filename(filename: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Sanitize and truncate a client-provided filename."""
    sanitized = re.sub(r"[^\w\s\-\.]", "", filename)
    if not sanitized:
        return "downloaded_file"
    if "." in sanitized:
        name, ext = sanitized.rsplit(".", 1)
        ext = ext[:MAX_EXTENSION_LENGTH]
        return f"{name[: max_length - len(ext) - 1]}.{ext}"
    return sanitized[:max_length]


def validate_file_size(content_length: str | None, actual_size: int) -> None:
    """Validate file size against maximum allowed."""
    max_size_mb = MAX_FILE_SIZE / 1024 / 1024
    if content_length:
        try:
            if int(content_length) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {max_size_mb:.0f}MB",
                )
        except ValueError:
            logger.warning(f"Invalid content-length header: {content_length}")

    if actual_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size_mb:.0f}MB",
        )


def validate_mime_type(content_type: str) -> None:
    """Validate MIME type against allowed OCR inputs."""
    if content_type not in ALLOWED_MIME_TYPES:
        allowed = ", ".join(ALLOWED_MIME_TYPES)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed types: {allowed}",
        )


async def download_file_from_url(url: str) -> tuple[bytes, str, str]:
    """Download a URL file with size and MIME validation."""
    validate_url(url)

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("GET", url, follow_redirects=True, timeout=30.0) as response:
                response.raise_for_status()
                validate_file_size(response.headers.get("content-length"), 0)

                content_buffer = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    content_buffer.extend(chunk)
                    validate_file_size(None, len(content_buffer))

                content = bytes(content_buffer)
                content_type = response.headers.get("content-type")

            content_type = _resolve_content_type(url, content, content_type)
            validate_mime_type(content_type)
            return content, _extract_filename_from_url(url), content_type

        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Error downloading file from URL: {str(exc)}",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Error downloading file from URL: Status {exc.response.status_code}",
            ) from exc


def parse_markdown_json(text: str) -> dict[str, Any] | str:
    """Parse JSON that may be wrapped in markdown fences."""
    if not text or not isinstance(text, str):
        return text

    cleaned = text.strip()
    extracted_json = _extract_markdown_json(cleaned) or cleaned
    try:
        return json.loads(extracted_json)
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse JSON from text: {exc}")
        return text


def is_gemini_3_model(model_name: str) -> bool:
    """Detect whether a model belongs to the Gemini 3 family."""
    model_lower = model_name.lower()
    return any(pattern in model_lower for pattern in GEMINI_3_PATTERNS)


def build_generation_config(
    model_name: str,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_output_tokens: int | None = None,
    thinking_budget: int | None = None,
    thinking_level: str | None = None,
    default_thinking_budget: int = -1,
    default_thinking_level: str = "low",
) -> types.GenerateContentConfig | None:
    """Build GenerateContentConfig with version-specific thinking support."""
    config_dict: dict[str, Any] = {}
    for key, value in {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "max_output_tokens": max_output_tokens,
    }.items():
        if value is not None:
            config_dict[key] = value

    thinking_config = _build_thinking_config(
        model_name=model_name,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
        default_thinking_budget=default_thinking_budget,
        default_thinking_level=default_thinking_level,
    )
    if thinking_config:
        config_dict["thinking_config"] = thinking_config

    return types.GenerateContentConfig(**config_dict) if config_dict else None


def _build_thinking_config(
    model_name: str,
    thinking_budget: int | None,
    thinking_level: str | None,
    default_thinking_budget: int,
    default_thinking_level: str,
) -> types.ThinkingConfig | None:
    if is_gemini_3_model(model_name):
        return _build_gemini_3_thinking_config(thinking_level, default_thinking_level)
    return _build_gemini_25_thinking_config(thinking_budget, default_thinking_budget)


def _build_gemini_3_thinking_config(
    thinking_level: str | None,
    default_level: str,
) -> types.ThinkingConfig | None:
    level = thinking_level if thinking_level is not None else default_level
    if level is None:
        logger.info("Using default Gemini 3 thinking behavior (high)")
        return None

    support = _thinking_config_support()
    if support["thinking_level"]:
        try:
            logger.info(f"Gemini 3 thinking mode: {level}")
            return types.ThinkingConfig(thinking_level=level)
        except Exception as exc:
            logger.warning(f"Failed to set thinking_level: {exc}")

    if support["include_thoughts"]:
        logger.info(
            f"Gemini 3 thinking mode: {level} (requested) -> include_thoughts=True (fallback)"
        )
        return types.ThinkingConfig(include_thoughts=True)

    logger.warning(f"ThinkingLevel not supported in current SDK version. Requested: {level}")
    return None


def _build_gemini_25_thinking_config(
    thinking_budget: int | None,
    default_budget: int,
) -> types.ThinkingConfig | None:
    budget = thinking_budget if thinking_budget is not None else default_budget
    if budget == 0:
        logger.info("Gemini 2.5 thinking mode disabled")
        return None
    if budget is not None and budget != -1:
        logger.info(f"Gemini 2.5 thinking mode with budget: {budget} tokens")
        return types.ThinkingConfig(include_thoughts=True, thinking_budget=budget)
    logger.info("Using default Gemini 2.5 thinking behavior")
    return None


def _thinking_config_support() -> dict[str, bool]:
    supported = {
        "thinking_level": False,
        "include_thoughts": False,
        "thinking_budget": False,
    }
    try:
        model_fields = types.ThinkingConfig.model_fields.keys()
        supported["thinking_level"] = "thinking_level" in model_fields
        supported["include_thoughts"] = "include_thoughts" in model_fields
        supported["thinking_budget"] = "thinking_budget" in model_fields
    except Exception as exc:
        logger.warning(f"Failed to inspect ThinkingConfig fields: {exc}")
    return supported


def _resolve_content_type(url: str, content: bytes, content_type: str | None) -> str:
    if _is_generic_content_type(content_type):
        content_type, _ = mimetypes.guess_type(url)
    if _is_generic_content_type(content_type):
        if content.startswith(b"%PDF-"):
            content_type = "application/pdf"
        elif content.startswith(b"\x89PNG\r\n\x1a\n"):
            content_type = "image/png"
        elif content.startswith(b"\xff\xd8\xff"):
            content_type = "image/jpeg"
        else:
            content_type = "application/octet-stream"
    return content_type.split(";")[0].strip().lower()


def _is_generic_content_type(content_type: str | None) -> bool:
    return (
        not content_type
        or content_type.startswith("application/octet-stream")
        or content_type == "binary/octet-stream"
    )


def _extract_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    return sanitize_filename(parsed.path.split("/")[-1])


def _extract_markdown_json(text: str) -> str | None:
    for pattern in MARKDOWN_PATTERNS:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return None
