"""V2 OCR engine: Schema-driven structured extraction."""

import concurrent.futures
from typing import Any

from schemas import ClassificationSchema, ClassifySegmentDocument, ExtractionSchema
from utils.gemini import parse_markdown_json
from utils.logging import get_logger
from utils.pdf import slice_pdf_multiple_ranges
from utils.schema_builder import (
    build_phase1_response_schema,
    build_phase2_response_schema,
)

from core.config import settings
from core.engine.base import BaseGeminiEngine
from core.prompts import PromptBuilder

logger = get_logger(__name__)


class OCRServiceV2(BaseGeminiEngine):
    """V2 OCR engine methods."""

    def run_prefilter_only(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Run only the prefilter check to determine if the document is valid.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            model_name: Optional model name override.

        Returns:
            Dict containing validation result.
        """
        chunk_bytes = file_bytes
        if mime_type.lower() == "application/pdf":
            page_count = self.detector._get_pdf_page_count(file_bytes)
            if page_count and page_count > 3:
                head_end = min(3, page_count)
                tail_start = max(1, page_count - 2)
                page_ranges = [(1, head_end)] + (
                    [(tail_start, page_count)] if tail_start > head_end else []
                )
                logger.info(f"Explicit prefilter: probing sampled pages {page_ranges}/{page_count}")
                chunk_bytes = slice_pdf_multiple_ranges(file_bytes, page_ranges)

        is_valid, usage_info = self.detector._call_model(
            file_bytes=chunk_bytes,
            file_name=file_name,
            mime_type=mime_type,
            model_name=model_name,
        )
        self._log_usage(usage_info, "run_prefilter_only")

        return {"is_valid_document": is_valid}

    def _classify_and_segment(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        extraction_schemas: list[ExtractionSchema | ClassificationSchema] | None = None,
        extract_all_documents: bool = False,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> tuple[dict[str, Any] | list[dict[str, Any]], dict[str, int]]:
        """Phase 1: Classify and segment documents in the file.

        Args:
            file_bytes: File content as bytes.
            file_name: Name of the file.
            mime_type: MIME type of the file.
            extraction_schemas: Optional list of extraction schemas.
            extract_all_documents: Whether to extract all document types.
            model_name: Optional model name override.
            temperature: Controls randomness.
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.

        Returns:
            Tuple of (segmentation result dict, usage info dict).
        """
        document_part = self._prepare_document_part(file_bytes, file_name, mime_type)
        prompt = PromptBuilder.build_phase1_prompt(extraction_schemas, extract_all_documents)
        response_json_schema = build_phase1_response_schema(
            extraction_schemas, extract_all_documents
        )

        text, usage_info = self._call_model(
            document_part,
            prompt,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            response_mime_type="application/json",
            response_json_schema=response_json_schema,
        )
        self._log_usage(usage_info, "_classify_and_segment")

        result = parse_markdown_json(text)
        if not isinstance(result, dict):
            logger.warning("Phase 1 returned non-object payload. Marking file as invalid.")
            return {"documents": []}, usage_info

        if not isinstance(result.get("documents"), list):
            result["documents"] = []

        return result, usage_info

    def run_classify_and_segment(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        extraction_schemas: list[ExtractionSchema | ClassificationSchema] | None = None,
        extract_all_documents: bool = False,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> dict[str, Any]:
        """Run Phase 1 classification and segmentation only.

        This is a wrapper around `_classify_and_segment` designed for the standalone
        classify and segment API endpoint.

        Returns:
            Dict containing the 'documents' array with classification and boundaries.
        """
        segmentation_res, _ = self._classify_and_segment(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            extraction_schemas=extraction_schemas,
            extract_all_documents=extract_all_documents,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )

        if not isinstance(segmentation_res, dict):
            logger.warning("Phase 1 failed or returned unexpected format. Marking file as invalid.")
            return {"documents": []}

        docs = segmentation_res.get("documents", [])
        if not isinstance(docs, list):
            return {"documents": []}

        return segmentation_res

    def _extract_segment(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        schema: ExtractionSchema | None,
        extract_all_fields: bool = False,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Phase 2: Extract data from a single document segment.

        Args:
            file_bytes: File content as bytes (may be sliced PDF).
            file_name: Name of the file.
            mime_type: MIME type of the file.
            schema: Extraction schema for this document type.
            extract_all_fields: Whether to extract all fields beyond schema.
            model_name: Optional model name override.
            temperature: Controls randomness.
            top_p: Nucleus sampling threshold.
            top_k: Top-k sampling parameter.
            max_output_tokens: Maximum tokens to generate.
            thinking_budget: Token budget for Gemini 2.5.
            thinking_level: Thinking level for Gemini 3.

        Returns:
            Tuple of (extraction result dict, usage info dict).
        """
        document_part = self._prepare_document_part(file_bytes, file_name, mime_type)
        prompt = PromptBuilder.build_phase2_prompt(
            schema,
            extract_all_fields,
        )
        response_json_schema = build_phase2_response_schema(schema, extract_all_fields)

        text, usage_info = self._call_model(
            document_part,
            prompt,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            response_mime_type="application/json",
            response_json_schema=response_json_schema,
        )
        self._log_usage(usage_info, "_extract_segment")

        result = parse_markdown_json(text)
        if not isinstance(result, dict):
            logger.warning(f"Phase 2 extraction returned non-dict: {type(result)}")
            result = {"extracted_data": text}

        return result, usage_info

    def extract_classified_documents(
        self,
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
    ) -> dict[str, Any]:
        """Extract data from already-classified document segments."""
        schema_map = {s.document_code: s for s in extraction_schemas}
        high_accuracy_codes = _parse_config_csv(settings.OCR_HIGH_ACCURACY_DOCUMENT_CODES)

        logger.info(
            f"Phase 2: Starting parallel extraction for {len(documents)} documents "
            f"(max_workers={settings.GEMINI_MAX_CONCURRENT_EXTRACTIONS})"
        )

        extracted_documents = []
        total_input_tokens = 0
        total_output_tokens = 0
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.GEMINI_MAX_CONCURRENT_EXTRACTIONS
        ) as executor:
            futures = [
                executor.submit(
                    self._extract_classified_document,
                    doc,
                    file_bytes,
                    file_name,
                    mime_type,
                    schema_map,
                    high_accuracy_codes,
                    extract_all_fields,
                    model_name,
                    temperature,
                    top_p,
                    top_k,
                    max_output_tokens,
                    thinking_budget,
                    thinking_level,
                )
                for doc in documents
            ]
            for future in futures:
                extracted_doc, usage = future.result()
                extracted_documents.append(extracted_doc)
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)

        total_tokens = total_input_tokens + total_output_tokens
        logger.info(
            f"Token Usage (Pipeline Total) - Input: {total_input_tokens:,}, "
            f"Output: {total_output_tokens:,}, Total: {total_tokens:,}"
        )

        return {"documents": extracted_documents}

    def _extract_classified_document(
        self,
        doc: ClassifySegmentDocument,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        schema_map: dict[str, ExtractionSchema],
        high_accuracy_codes: set[str],
        extract_all_fields: bool,
        model_name: str | None,
        temperature: float | None,
        top_p: float | None,
        top_k: int | None,
        max_output_tokens: int | None,
        thinking_budget: int | None,
        thinking_level: str | None,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        doc_data = doc.model_dump(exclude_none=True)
        doc_code = doc.document_code
        schema = schema_map.get(doc_code)
        start_page, end_page = _normalize_page_range(doc_data)

        chunk_bytes = file_bytes
        if mime_type.lower() == "application/pdf":
            chunk_bytes = slice_pdf_multiple_ranges(file_bytes, [(start_page, end_page)])

        logger.info(f"Phase 2: Extracting {doc_code} block (Pages {start_page}-{end_page})")
        doc_model = _resolve_phase2_model(doc_code, high_accuracy_codes, model_name)
        extracted_res, phase2_usage = self._extract_segment(
            chunk_bytes,
            file_name,
            mime_type,
            schema,
            extract_all_fields,
            model_name=doc_model,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
        )

        doc_data["extracted_data"] = extracted_res if isinstance(extracted_res, dict) else {}
        return doc_data, phase2_usage


def _normalize_page_range(doc: dict[str, Any]) -> tuple[int, int]:
    """Normalize model-provided page range for per-document extraction."""
    start_page = _coerce_positive_int(doc.get("start_page"), 1)
    end_page = _coerce_positive_int(doc.get("end_page"), start_page)
    if end_page < start_page:
        logger.warning(
            f"Invalid page range {start_page}-{end_page}; using start page for both bounds."
        )
        end_page = start_page
    return start_page, end_page


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_config_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _resolve_phase2_model(
    doc_code: str,
    high_accuracy_codes: set[str],
    requested_model: str | None,
) -> str | None:
    high_accuracy_model = settings.OCR_HIGH_ACCURACY_MODEL
    if doc_code in high_accuracy_codes and requested_model != high_accuracy_model:
        logger.info(f"Using high-accuracy model '{high_accuracy_model}' for {doc_code} in Phase 2")
        return high_accuracy_model
    return requested_model
