"""OCR engine implementation using Google Gemini API."""

import os
import tempfile
import time
from typing import Any, Final

import fitz  # PyMuPDF
import google.genai as genai
from google.genai import types
from utils.gemini import build_generation_config, parse_markdown_json
from utils.logging import get_logger

from core.config import settings

logger = get_logger(__name__)

MAX_DISPLAY_NAME_LENGTH: Final[int] = 150


class GeminiConfigError(Exception):
    """Exception raised for Gemini configuration errors."""

    pass


class DocumentDetector:
    """Helper class to handle early rejection of invalid documents before OCR."""

    def __init__(self, ocr_service: "BaseGeminiEngine"):
        self.ocr_service = ocr_service

    @staticmethod
    def _get_pdf_page_count(file_bytes: bytes) -> int | None:
        """Get the number of pages in a PDF file.

        Args:
            file_bytes: PDF file content as bytes.

        Returns:
            Number of pages, or None if the file cannot be read.
        """
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                return len(doc)
        except Exception as e:
            logger.warning(f"Failed to read PDF page count for detect prefilter: {e}")
            return None

    @staticmethod
    def _coerce_result(value: Any) -> bool | None:
        """Coerce model output to a boolean validity flag.

        Args:
            value: Raw model output (bool, dict, or string).

        Returns:
            Boolean validity flag, or None if the value cannot be interpreted.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, dict) and isinstance(value.get("is_valid_document"), bool):
            return value["is_valid_document"]
        if isinstance(value, str):
            normalized = value.strip().strip("`").lower()
            if normalized in {"true", "false"}:
                return normalized == "true"
            if "false" in normalized and "true" not in normalized:
                return False
            if "true" in normalized and "false" not in normalized:
                return True
        return None

    def _call_model(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        model_name: str | None,
    ) -> tuple[bool, dict[str, int]]:
        """Call Gemini model to determine document validity.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            model_name: Optional model name override.

        Returns:
            Tuple of (is_valid, usage_info).
        """
        document_part = self.ocr_service._prepare_document_part(file_bytes, file_name, mime_type)

        schema = {
            "type": "object",
            "properties": {
                "is_valid_document": {
                    "type": "boolean",
                    "description": (
                        "True if document is a medical claim, health record, "
                        "or personal ID (CCCD/Passport/License). "
                        "False if out of scope/irrelevant."
                    ),
                }
            },
            "required": ["is_valid_document"],
        }

        text, usage = self.ocr_service._call_model(
            document_part,
            prompt="Analyze the document and return the result according to schema.",
            model_name=model_name,
            temperature=0.0,
            max_output_tokens=32,
            thinking_budget=0,
            thinking_level="minimal",
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        self.ocr_service._log_usage(usage, "_detect_document_domain")

        parsed = parse_markdown_json(text)
        is_valid = self._coerce_result(parsed) or self._coerce_result(text)

        if is_valid is None:
            logger.warning("Detect prefilter returned invalid payload. Continue with segmentation.")
            return True, usage
        return is_valid, usage

    def run_prefilter(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        model_name: str | None = None,
    ) -> tuple[bool, dict[str, int]]:
        """Samples 3+ page PDFs to detect if they are valid before heavy segmentation.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            model_name: Optional model name override.

        Returns:
            Tuple of (should_skip, usage_info).
        """
        from utils.pdf import slice_pdf_multiple_ranges

        usage = self.ocr_service._empty_usage()
        if mime_type.lower() != "application/pdf":
            return False, usage

        page_count = self._get_pdf_page_count(file_bytes)
        if not page_count or page_count < 3:
            return False, usage

        head_end = min(3, page_count)
        tail_start = max(1, page_count - 2)
        page_ranges = [(1, head_end)] + (
            [(tail_start, page_count)] if tail_start > head_end else []
        )

        logger.info(f"Document detect prefilter: probing sampled pages {page_ranges}/{page_count}")
        sample_bytes = slice_pdf_multiple_ranges(file_bytes, page_ranges)
        is_valid, detect_usage = self._call_model(sample_bytes, file_name, mime_type, model_name)
        self.ocr_service._accumulate_usage(usage, detect_usage)

        if not is_valid:
            logger.info("Document detect prefilter marked file as invalid. Skipping segmentation.")
            return True, usage
        return False, usage


class BaseGeminiEngine:
    """Base class for Gemini OCR engine containing shared logic."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise GeminiConfigError("Missing GEMINI_API_KEY. Set env var or pass via UI.")
        self.client = genai.Client(api_key=self.api_key)
        self.detector = DocumentDetector(self)

    @staticmethod
    def _empty_usage() -> dict[str, int]:
        """Return an empty token usage dictionary."""
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    @staticmethod
    def _accumulate_usage(target: dict[str, int], source: dict[str, Any]) -> None:
        """Accumulate token usage from source into target.

        Args:
            target: Target usage dict to update in-place.
            source: Source usage dict to add from.
        """
        target.setdefault("input_tokens", 0)
        target.setdefault("output_tokens", 0)
        target.setdefault("total_tokens", 0)
        target["input_tokens"] += int(source.get("input_tokens", 0) or 0)
        target["output_tokens"] += int(source.get("output_tokens", 0) or 0)
        target["total_tokens"] += int(source.get("total_tokens", 0) or 0)

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
            # WHY: Truncate display_name to avoid API issues with long filenames
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

    def _prepare_document_part(
        self, file_bytes: bytes, file_name: str, mime_type: str
    ) -> types.Part | Any:
        """Prepare the document for Gemini API either as inline bytes or by uploading.

        Small files (below GEMINI_MAX_INLINE_IN_BYTES) are sent as inline bytes.
        Large files are uploaded to the Files API.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.

        Returns:
            A types.Part object with inline data for small files, or an uploaded file object.
        """
        start_time = time.time()

        if len(file_bytes) <= settings.GEMINI_MAX_INLINE_IN_BYTES:
            logger.debug(
                f"File size {len(file_bytes)} bytes is <= "
                f"{settings.GEMINI_MAX_INLINE_IN_BYTES} bytes threshold. Using inline bytes."
            )
            result = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            elapsed = time.time() - start_time
            logger.info(
                f"Prepare document (inline bytes) for {file_name} took {elapsed:.4f} seconds"
            )
            return result

        logger.debug(
            f"File size {len(file_bytes)} bytes exceeds "
            f"{settings.GEMINI_MAX_INLINE_IN_BYTES} bytes threshold. Uploading to Files API."
        )
        result = self._upload_temp_file(file_bytes, file_name, mime_type)
        elapsed = time.time() - start_time
        logger.info(
            f"Prepare document (Files API upload) for {file_name} took {elapsed:.4f} seconds"
        )
        return result

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
        document_part,
        prompt: str,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
        response_mime_type: str | None = None,
        response_json_schema: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, int]]:
        """Call Gemini model with document and prompt.

        Supports both free-text and structured JSON output modes.

        Args:
            document_part: Uploaded file object or types.Part.
            prompt: Text prompt for the model.
            model_name: Optional model name override.
            temperature: Controls randomness (0.0-2.0).
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.
            response_mime_type: Optional mime type (e.g. application/json).
            response_json_schema: Optional JSON schema for structured output.

        Returns:
            Tuple of (response text, usage info dict).
        """
        contents = [document_part]
        if prompt:
            contents.append(types.Part.from_text(text=prompt))

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

        # WHY: V2 structured output requires merging JSON schema config
        # into GenerateContentConfig alongside thinking/generation params
        if response_mime_type or response_json_schema:
            extra: dict[str, Any] = {}
            if response_mime_type:
                extra["response_mime_type"] = response_mime_type
            if response_json_schema:
                extra["response_json_schema"] = response_json_schema

            if config:
                for attr in (
                    "temperature",
                    "top_p",
                    "top_k",
                    "max_output_tokens",
                    "thinking_config",
                ):
                    val = getattr(config, attr, None)
                    if val is not None:
                        extra[attr] = val

            config = types.GenerateContentConfig(**extra)

        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        text = getattr(response, "text", "") or ""
        usage_info = self._extract_usage_info(response)

        return text, usage_info

    @staticmethod
    def _log_usage(usage_metadata: Any, method_name: str) -> None:
        """Log token usage from a Gemini response.

        Handles both raw usage_metadata objects and pre-extracted dicts.

        Args:
            usage_metadata: The usage_metadata attribute from a Gemini response, or a dict.
            method_name: Name of the calling method for log identification.
        """
        if not usage_metadata:
            return
        if isinstance(usage_metadata, dict):
            input_tokens = usage_metadata.get(
                "input_tokens", usage_metadata.get("prompt_token_count", 0)
            )
            output_tokens = usage_metadata.get(
                "output_tokens", usage_metadata.get("candidates_token_count", 0)
            )
            total_tokens = usage_metadata.get(
                "total_tokens", usage_metadata.get("total_token_count", 0)
            )
        else:
            input_tokens = getattr(usage_metadata, "prompt_token_count", 0)
            output_tokens = getattr(usage_metadata, "candidates_token_count", 0)
            total_tokens = getattr(usage_metadata, "total_token_count", 0)
        logger.info(
            f"Token Usage ({method_name}) - Input: {input_tokens:,}, "
            f"Output: {output_tokens:,}, Total: {total_tokens:,}"
        )

    def _log_token_usage(self, operation: str, usage_info: dict[str, int]) -> None:
        """Log token usage information (alias for _log_usage).

        Args:
            operation: Name of the operation.
            usage_info: Dictionary with token usage information.
        """
        self._log_usage(usage_info, operation)
