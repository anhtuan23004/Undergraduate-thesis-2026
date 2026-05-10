"""OCR engine implementation using Google Gemini API."""

from typing import Any, Final

from utils.gemini import parse_markdown_json
from utils.logging import get_logger

from core.engine.base import BaseGeminiEngine

logger = get_logger(__name__)

# Prompt templates
RAW_TEXT_PROMPT: Final[str] = (
    "You are an OCR engine. Read the document and output the raw text,\n"
    "preserving natural reading order as much as possible.\n"
)

FIELDS_PROMPT: Final[str] = (
    "Extract key fields from the document. If not specified otherwise,\n"
    "return a concise JSON object with clearly named keys."
)

DOCUMENT_PROMPT: Final[
    str
] = "Analyze the document structure and return a structured JSON representation of its content."

DEFAULT_FIELDS_USER_PROMPT: Final[str] = "Extract key fields and return JSON."
DEFAULT_DOCUMENT_USER_PROMPT: Final[str] = "Extract document structure as JSON."

MAX_DISPLAY_NAME_LENGTH: Final[int] = 150


class GeminiConfigError(Exception):
    """Exception raised for Gemini configuration errors."""

    pass


class OCRServiceV1(BaseGeminiEngine):
    """V1 OCR engine methods."""

    def parse_raw(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        prompt: str,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> str:
        """Extract raw text from an image or PDF.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            prompt: Optional user prompt.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.

        Returns:
            Extracted raw text.
        """
        uploaded = self._upload_temp_file(file_bytes, file_name, mime_type)

        full_prompt = RAW_TEXT_PROMPT
        if prompt:
            full_prompt = f"{RAW_TEXT_PROMPT}\nUser prompt (optional): {prompt}"

        text, usage_info = self._call_model(
            uploaded,
            full_prompt,
            model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )

        self._log_token_usage("parse_raw", usage_info)
        return text

    def parse_fields(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        prompt: str,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> Any:
        """Extract structured fields from a document.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            prompt: User prompt for extraction.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.

        Returns:
            Extracted fields (typically JSON dict or string).
        """
        uploaded = self._upload_temp_file(file_bytes, file_name, mime_type)

        user_prompt = prompt or DEFAULT_FIELDS_USER_PROMPT
        full_prompt = f"{FIELDS_PROMPT}\n\nUser prompt: {user_prompt}"

        text, usage_info = self._call_model(
            uploaded,
            full_prompt,
            model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )

        self._log_token_usage("parse_fields", usage_info)
        return parse_markdown_json(text)

    def parse_document(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        prompt: str,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> Any:
        """Extract document structure from a document.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            prompt: User prompt for extraction.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.

        Returns:
            Extracted document structure (typically JSON dict or string).
        """
        uploaded = self._upload_temp_file(file_bytes, file_name, mime_type)

        user_prompt = prompt or DEFAULT_DOCUMENT_USER_PROMPT
        full_prompt = f"{DOCUMENT_PROMPT}\n\nUser prompt: {user_prompt}"

        text, usage_info = self._call_model(
            uploaded,
            full_prompt,
            model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )

        self._log_token_usage("parse_document", usage_info)
