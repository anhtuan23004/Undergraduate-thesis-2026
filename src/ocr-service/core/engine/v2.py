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

    @staticmethod
    def _coerce_page_range(value: Any) -> tuple[int, int] | None:
        if isinstance(value, dict):
            raw_start = value.get("start_page")
            raw_end = value.get("end_page")
        elif isinstance(value, list | tuple) and len(value) == 2:
            raw_start, raw_end = value
        else:
            return None

        try:
            start_page = int(raw_start)
            end_page = int(raw_end)
        except (TypeError, ValueError):
            return None

        if start_page < 1 or end_page < 1:
            return None

        return (min(start_page, end_page), max(start_page, end_page))

    @staticmethod
    def _expand_page_ranges(page_ranges: list[tuple[int, int]]) -> list[int]:
        pages = []
        for start_page, end_page in page_ranges:
            pages.extend(range(start_page, end_page + 1))
        return pages

    @staticmethod
    def _dedupe_page_order(page_order: list[int]) -> list[int]:
        pages = []
        seen = set()
        for page in page_order:
            if page in seen:
                continue
            seen.add(page)
            pages.append(page)
        return pages

    @staticmethod
    def _compress_page_order(page_order: list[int]) -> list[tuple[int, int]]:
        if not page_order:
            return []

        ranges = []
        range_start = page_order[0]
        previous_page = page_order[0]

        for page in page_order[1:]:
            if page == previous_page + 1:
                previous_page = page
                continue

            ranges.append((range_start, previous_page))
            range_start = page
            previous_page = page

        ranges.append((range_start, previous_page))
        return ranges

    @classmethod
    def _get_document_page_ranges(cls, doc: dict[str, Any]) -> list[tuple[int, int]]:
        raw_ranges = doc.get("page_ranges")
        ranges = []
        if isinstance(raw_ranges, list):
            for raw_range in raw_ranges:
                page_range = cls._coerce_page_range(raw_range)
                if page_range:
                    ranges.append(page_range)

        if ranges:
            return ranges

        return [_normalize_page_range(doc)]

    @classmethod
    def _get_document_page_order(cls, doc: dict[str, Any]) -> list[int]:
        raw_order = doc.get("page_order")
        if isinstance(raw_order, list):
            pages = []
            for raw_page in raw_order:
                try:
                    page = int(raw_page)
                except (TypeError, ValueError):
                    continue
                if page > 0:
                    pages.append(page)
            if pages:
                return cls._dedupe_page_order(pages)

        page_ranges = cls._get_document_page_ranges(doc)
        return cls._dedupe_page_order(cls._expand_page_ranges(page_ranges))

    @staticmethod
    def _coerce_duplicate_page(value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None

        try:
            page = int(value.get("page"))
            duplicate_of = int(value.get("duplicate_of"))
        except (TypeError, ValueError):
            return None

        if page < 1 or duplicate_of < 1 or page == duplicate_of:
            return None

        return {"page": page, "duplicate_of": duplicate_of}

    @classmethod
    def _get_document_duplicate_pages(cls, doc: dict[str, Any]) -> list[dict[str, int]]:
        raw_duplicates = doc.get("duplicate_pages")
        duplicates = []
        seen = set()

        if not isinstance(raw_duplicates, list):
            return duplicates

        for raw_duplicate in raw_duplicates:
            duplicate = cls._coerce_duplicate_page(raw_duplicate)
            if not duplicate:
                continue

            key = (duplicate["page"], duplicate["duplicate_of"])
            if key in seen:
                continue

            seen.add(key)
            duplicates.append(duplicate)

        return duplicates

    @classmethod
    def _normalize_page_aware_segments(cls, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for doc in docs:
            if not isinstance(doc, dict):
                continue

            raw_page_order = cls._get_document_page_order(doc)
            canonical_candidates = set(raw_page_order)
            duplicate_candidates = [
                duplicate
                for duplicate in cls._get_document_duplicate_pages(doc)
                if duplicate["duplicate_of"] in canonical_candidates
            ]
            duplicate_page_numbers = {duplicate["page"] for duplicate in duplicate_candidates}
            page_order = [page for page in raw_page_order if page not in duplicate_page_numbers]

            if not page_order:
                page_order = raw_page_order
                duplicate_candidates = []

            canonical_pages = set(page_order)
            duplicate_pages = []
            seen_duplicate_pages = set()
            for duplicate in duplicate_candidates:
                duplicate_page = duplicate["page"]
                if duplicate["duplicate_of"] not in canonical_pages:
                    continue
                if duplicate_page in canonical_pages:
                    continue
                if duplicate_page in seen_duplicate_pages:
                    continue

                seen_duplicate_pages.add(duplicate_page)
                duplicate_pages.append(duplicate)

            page_ranges = cls._compress_page_order(page_order)
            if not page_ranges:
                page_ranges = cls._get_document_page_ranges(doc)
                page_order = cls._expand_page_ranges(page_ranges)
                duplicate_pages = []

            doc["page_ranges"] = [[start, end] for start, end in page_ranges]
            doc["page_order"] = page_order
            doc["duplicate_pages"] = duplicate_pages

            trace_pages = page_order + [duplicate["page"] for duplicate in duplicate_pages]
            doc["start_page"] = min(trace_pages) if trace_pages else doc.get("start_page", 1)
            doc["end_page"] = max(trace_pages) if trace_pages else doc.get("end_page", 1)

        return sorted(
            docs,
            key=lambda doc: (
                min(doc.get("page_order") or [doc.get("start_page", 1)])
                if isinstance(doc, dict)
                else 1,
                doc.get("end_page", 1) if isinstance(doc, dict) else 1,
            ),
        )

    @classmethod
    def _get_document_slice_ranges(cls, doc: dict[str, Any]) -> list[tuple[int, int]]:
        page_order = cls._get_document_page_order(doc)
        return cls._compress_page_order(page_order) or cls._get_document_page_ranges(doc)

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

        result["documents"] = self._normalize_page_aware_segments(result["documents"])

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
        page_ranges = self._get_document_slice_ranges(doc_data)

        chunk_bytes = file_bytes
        if mime_type.lower() == "application/pdf":
            chunk_bytes = slice_pdf_multiple_ranges(file_bytes, page_ranges)

        pages_str = ", ".join(f"{start_page}-{end_page}" for start_page, end_page in page_ranges)
        logger.info(f"Phase 2: Extracting {doc_code} block (Pages {pages_str})")
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
