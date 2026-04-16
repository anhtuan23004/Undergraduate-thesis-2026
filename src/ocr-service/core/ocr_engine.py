"""OCR engine implementation using Google Gemini API."""

import os
import tempfile
from typing import Any, Final

import google.genai as genai
from app.config import settings
from google.genai import types
from utils.logging import get_logger

from core.utils import build_generation_config, parse_markdown_json

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


class GeminiOCRService:
    """Service for OCR operations using Google Gemini API.

    Args:
        api_key: Optional API key override.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise GeminiConfigError("Missing GEMINI_API_KEY. Set env var or pass via UI.")
        self.client = genai.Client(api_key=self.api_key)

    def _upload_temp_file(self, file_bytes: bytes, file_name: str, mime_type: str) -> types.File:
        """Upload file bytes to Gemini Files API.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.

        Returns:
            Uploaded file object.
        """
        # Preserve file extension for proper MIME type detection
        suffix = ""
        if "." in file_name:
            suffix = file_name[file_name.rfind(".") :]

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            path = tmp.name

        try:
            # Truncate display_name to avoid API issues with long filenames
            display_name = (
                file_name[:MAX_DISPLAY_NAME_LENGTH]
                if len(file_name) > MAX_DISPLAY_NAME_LENGTH
                else file_name
            )

            return self.client.files.upload(
                file=path,
                config=types.UploadFileConfig(display_name=display_name, mime_type=mime_type),
            )
        finally:
            # Clean up temporary file
            try:
                os.remove(path)
            except OSError as exc:
                logger.warning(f"Failed to remove temporary file {path}: {exc}")

    def _build_contents(
        self, uploaded_file: types.File, prompt: str
    ) -> list[types.File | types.Part]:
        """Build content list for model generation.

        Args:
            uploaded_file: Uploaded file object.
            prompt: Text prompt for the model.

        Returns:
            List of content items.
        """
        contents: list[types.File | types.Part] = [uploaded_file]
        if prompt:
            contents.append(types.Part.from_text(text=prompt))
        return contents

    def _extract_usage_info(self, response: Any) -> dict[str, int]:
        """Extract token usage information from response.

        Args:
            response: The model response object.

        Returns:
            Dictionary with token usage information.
        """
        usage_metadata = getattr(response, "usage_metadata", None)
        if not usage_metadata:
            return {}

        return {
            "input_tokens": getattr(usage_metadata, "prompt_token_count", 0),
            "output_tokens": getattr(usage_metadata, "candidates_token_count", 0),
            "total_tokens": getattr(usage_metadata, "total_token_count", 0),
        }

    def _call_model(
        self,
        uploaded_file: types.File,
        prompt: str,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> tuple[str, dict[str, int]]:
        """Call Gemini model with uploaded file and prompt.

        Args:
            uploaded_file: Uploaded file object.
            prompt: Text prompt for the model.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.

        Returns:
            Tuple of (response text, usage info dict).
        """
        contents = self._build_contents(uploaded_file, prompt)
        model = model_name or settings.GEMINI_MODEL

        config = build_generation_config(
            model_name=model,
            temperature=temperature if temperature is not None else settings.GEMINI_TEMPERATURE,
            top_p=top_p if top_p is not None else settings.GEMINI_TOP_P,
            top_k=top_k if top_k is not None else settings.GEMINI_TOP_K,
            max_output_tokens=max_output_tokens
            if max_output_tokens is not None
            else settings.GEMINI_MAX_OUTPUT_TOKENS,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            default_thinking_budget=settings.GEMINI_THINKING_BUDGET,
            default_thinking_level=settings.GEMINI_THINKING_LEVEL,
        )

        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        text = getattr(response, "text", "") or ""
        usage_info = self._extract_usage_info(response)

        return text, usage_info

    def _log_token_usage(self, operation: str, usage_info: dict[str, int]) -> None:
        """Log token usage information.

        Args:
            operation: Name of the operation.
            usage_info: Dictionary with token usage information.
        """
        if not usage_info:
            return

        logger.info(
            f"Token Usage ({operation}) - Input: {usage_info.get('input_tokens', 0):,}, "
            f"Output: {usage_info.get('output_tokens', 0):,}, "
            f"Total: {usage_info.get('total_tokens', 0):,}"
        )

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
        return parse_markdown_json(text)
