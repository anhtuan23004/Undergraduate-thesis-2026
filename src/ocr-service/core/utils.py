"""Core utility functions for the OCR service."""

import json
import mimetypes
import re
from typing import Any, Dict, Final, Optional, Union
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from google.genai import types

from utils.logging import get_logger

logger = get_logger(__name__)

# Security constants
ALLOWED_MIME_TYPES: Final[set[str]] = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/pdf",
}
MAX_FILE_SIZE: Final[int] = 50 * 1024 * 1024  # 50MB
MAX_FILENAME_LENGTH: Final[int] = 100
MAX_EXTENSION_LENGTH: Final[int] = 10

# Gemini model detection patterns
GEMINI_3_PATTERNS: Final[tuple[str, ...]] = (
    "gemini-3",
    "gemini3",
    "gemini-exp-",
)

# Markdown JSON extraction patterns
MARKDOWN_PATTERNS: Final[tuple[str, ...]] = (
    r"```(?:json)?\s*\n?(.*?)\n?```",  # ```json ... ``` or ``` ... ```
    r"`([^`]+)`",  # Single backticks `...`
)


def validate_url(url: str) -> None:
    """Validate URL format and scheme to prevent SSRF attacks.

    Args:
        url: The URL to validate.

    Raises:
        HTTPException: If URL is invalid.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400,
                detail="Only HTTP and HTTPS URLs are allowed",
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid URL format") from exc


def sanitize_filename(filename: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Sanitize and truncate filename to prevent path traversal and length issues.

    Args:
        filename: The filename to sanitize.
        max_length: Maximum length for the filename.

    Returns:
        Sanitized and truncated filename.
    """
    # Remove path traversal characters and keep only safe characters
    sanitized = re.sub(r"[^\w\s\-\.]", "", filename)

    if not sanitized:
        return "downloaded_file"

    # Handle files with extension
    if "." in sanitized:
        name, ext = sanitized.rsplit(".", 1)
        ext = ext[:MAX_EXTENSION_LENGTH]
        max_name_length = max_length - len(ext) - 1
        name = name[:max_name_length] if len(name) > max_name_length else name
        return f"{name}.{ext}"

    # No extension, just truncate
    return sanitized[:max_length]


def validate_file_size(content_length: Optional[str], actual_size: int) -> None:
    """Validate file size against maximum allowed.

    Args:
        content_length: Content-Length header value (if present).
        actual_size: Actual size of the content in bytes.

    Raises:
        HTTPException: If file size exceeds limit.
    """
    max_size_mb = MAX_FILE_SIZE / 1024 / 1024

    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size_mb:.0f}MB",
        )

    if actual_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size_mb:.0f}MB",
        )


def validate_mime_type(content_type: str) -> None:
    """Validate MIME type against allowed types.

    Args:
        content_type: The MIME type to validate.

    Raises HTTPException:
        If MIME type is not allowed.
    """
    if content_type not in ALLOWED_MIME_TYPES:
        allowed = ", ".join(ALLOWED_MIME_TYPES)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed types: {allowed}",
        )


def extract_filename_from_url(url: str) -> str:
    """Extract and sanitize filename from URL.

    Args:
        url: The URL to extract filename from.

    Returns:
        Sanitized filename.
    """
    parsed = urlparse(url)
    filename = parsed.path.split("/")[-1]
    return sanitize_filename(filename)


async def download_file_from_url(url: str) -> tuple[bytes, str, str]:
    """Download a file from a URL with security validations.

    Args:
        url: The URL to download from.

    Returns:
        Tuple of (content bytes, filename, content type).

    Raises:
        HTTPException: If download fails or validation fails.
    """
    validate_url(url)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()

            content_length = response.headers.get("content-length")
            validate_file_size(content_length, len(response.content))

            content_type = response.headers.get("content-type")
            if not content_type:
                content_type, _ = mimetypes.guess_type(url)
            if not content_type:
                content_type = "application/octet-stream"

            validate_mime_type(content_type)

            filename = extract_filename_from_url(url)
            return response.content, filename, content_type

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


def parse_markdown_json(text: str) -> Union[Dict[str, Any], str]:
    """Parse JSON string that might be wrapped in markdown code blocks.

    Args:
        text: Text that might contain markdown-wrapped JSON.

    Returns:
        Parsed JSON as dict if successful, otherwise returns the original text.
    """
    if not text or not isinstance(text, str):
        return text

    text = text.strip()

    # Try to extract JSON from markdown code blocks
    extracted_json = None
    for pattern in MARKDOWN_PATTERNS:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            extracted_json = match.group(1).strip()
            break

    # If no markdown wrapper found, use the whole text
    if not extracted_json:
        extracted_json = text

    # Try to parse as JSON
    try:
        return json.loads(extracted_json)
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse JSON from text: {exc}")
        return text


def is_gemini_3_model(model_name: str) -> bool:
    """Detect if model is Gemini 3.x series.

    Args:
        model_name: Name of the model.

    Returns:
        True if Gemini 3.x, False otherwise.
    """
    model_lower = model_name.lower()
    return any(pattern in model_lower for pattern in GEMINI_3_PATTERNS)


def get_thinking_config_support() -> Dict[str, bool]:
    """Check which thinking features are supported by the installed SDK."""
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


# Cache supported features at module load time
THINKING_SUPPORT: Final[Dict[str, bool]] = get_thinking_config_support()


def build_gemini_3_thinking_config(
    thinking_level: Optional[str],
    default_level: str,
) -> Optional[types.ThinkingConfig]:
    """Build ThinkingConfig for Gemini 3.x models.

    Args:
        thinking_level: Requested thinking level.
        default_level: Default thinking level if none specified.

    Returns:
        ThinkingConfig if applicable, None otherwise.
    """
    level = thinking_level if thinking_level is not None else default_level

    if level is None:
        logger.info("Using default Gemini 3 thinking behavior (high)")
        return None

    # Try thinking_level if supported
    if THINKING_SUPPORT["thinking_level"]:
        try:
            logger.info(f"Gemini 3 thinking mode: {level}")
            return types.ThinkingConfig(thinking_level=level)
        except Exception as exc:
            logger.warning(f"Failed to set thinking_level: {exc}")

    # Fallback to include_thoughts
    if THINKING_SUPPORT["include_thoughts"]:
        logger.info(
            f"Gemini 3 thinking mode: {level} (requested) -> include_thoughts=True (fallback)"
        )
        return types.ThinkingConfig(include_thoughts=True)

    # No support found
    logger.warning(
        f"ThinkingLevel not supported in current SDK version. Requested: {level}"
    )
    logger.info("Using default Gemini 3 thinking behavior (high)")
    return None


def build_gemini_25_thinking_config(
    thinking_budget: Optional[int],
    default_budget: int,
) -> Optional[types.ThinkingConfig]:
    """Build ThinkingConfig for Gemini 2.5 models.

    Args:
        thinking_budget: Requested thinking budget.
        default_budget: Default thinking budget if none specified.

    Returns:
        ThinkingConfig if applicable, None otherwise.
    """
    budget = thinking_budget if thinking_budget is not None else default_budget

    if budget == 0:
        logger.info("Gemini 2.5 thinking mode disabled")
        return None

    if budget is not None and budget != -1:  # Specific budget > 0
        logger.info(f"Gemini 2.5 thinking mode with budget: {budget} tokens")
        return types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=budget,
        )

    logger.info("Using default Gemini 2.5 thinking behavior")
    return None


def build_thinking_config(
    model_name: str,
    thinking_budget: Optional[int],
    thinking_level: Optional[str],
    default_thinking_budget: int,
    default_thinking_level: str,
) -> Optional[types.ThinkingConfig]:
    """Build ThinkingConfig based on model version and SDK support.

    Args:
        model_name: Name of the model.
        thinking_budget: Token budget for Gemini 2.5.
        thinking_level: Thinking level for Gemini 3.
        default_thinking_budget: Default budget for Gemini 2.5.
        default_thinking_level: Default level for Gemini 3.

    Returns:
        ThinkingConfig if applicable, None otherwise.
    """
    if is_gemini_3_model(model_name):
        return build_gemini_3_thinking_config(
            thinking_level, default_thinking_level
        )
    return build_gemini_25_thinking_config(
        thinking_budget, default_thinking_budget
    )


def build_generation_config(
    model_name: str,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    thinking_budget: Optional[int] = None,
    thinking_level: Optional[str] = None,
    default_thinking_budget: int = -1,
    default_thinking_level: str = "low",
) -> Optional[types.GenerateContentConfig]:
    """Build GenerateContentConfig with version-specific thinking support.

    Args:
        model_name: Name of the Gemini model.
        temperature: Controls randomness (0.0-2.0).
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum tokens to generate.
        thinking_budget: Token budget for Gemini 2.5.
        thinking_level: Thinking level for Gemini 3.
        default_thinking_budget: Default thinking budget for Gemini 2.5.
        default_thinking_level: Default thinking level for Gemini 3.

    Returns:
        GenerateContentConfig if any parameters are set, None otherwise.
    """
    config_dict: Dict[str, Any] = {}

    # Standard generation parameters
    if temperature is not None:
        config_dict["temperature"] = temperature
    if top_p is not None:
        config_dict["top_p"] = top_p
    if top_k is not None:
        config_dict["top_k"] = top_k
    if max_output_tokens is not None:
        config_dict["max_output_tokens"] = max_output_tokens

    # Version-specific thinking config
    thinking_config = build_thinking_config(
        model_name=model_name,
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
        default_thinking_budget=default_thinking_budget,
        default_thinking_level=default_thinking_level,
    )

    if thinking_config:
        config_dict["thinking_config"] = thinking_config

    return types.GenerateContentConfig(**config_dict) if config_dict else None
