"""V2 OCR engine: Schema-driven structured extraction."""

import concurrent.futures
from typing import Any

from schemas import ExtractionSchema
from utils.gemini import parse_markdown_json
from utils.logging import get_logger
from utils.pdf import slice_pdf_multiple_ranges
from utils.schema_builder import (
    build_phase1_response_schema,
    build_phase2_batch_response_schema,
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
        extraction_schemas: list[ExtractionSchema] | None = None,
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
        extraction_schemas: list[ExtractionSchema] | None = None,
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
        num_segments: int = 1,
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
            num_segments,
        )
        response_json_schema = (
            build_phase2_batch_response_schema(schema, extract_all_fields)
            if num_segments > 1
            else build_phase2_response_schema(schema, extract_all_fields)
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
        self._log_usage(usage_info, "_extract_segment")

        result = parse_markdown_json(text)
        if num_segments > 1:
            if not isinstance(result, list):
                logger.warning(
                    f"Expected list from batch extraction but got {type(result)}. Wrapping in list."
                )
                result = [result] if isinstance(result, dict) else []

            if len(result) < num_segments:
                result.extend([{} for _ in range(num_segments - len(result))])
            elif len(result) > num_segments:
                result = result[:num_segments]
            return result, usage_info

        if not isinstance(result, dict):
            logger.warning(f"Phase 2 extraction returned non-dict: {type(result)}")
            result = {"extracted_data": text}

        return result, usage_info

    def parse_with_schema_v2(  # noqa: C901
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        extraction_schemas: list[ExtractionSchema],
        extract_all_fields: bool = False,
        extract_all_documents: bool = False,
        model_name: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        max_output_tokens: int | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
    ) -> dict[str, Any]:
        """Run 2-stage schema-driven extraction (V2: Per-document slice and extract).

        Phase 1: Classify and identify document boundaries.
        Phase 2: Slice PDF based on boundaries (per segment) and extract in parallel.
        """
        total_input_tokens = 0
        total_output_tokens = 0

        # Phase 1: Classification and Segmentation
        logger.info(f"Phase 1: Segmenting document {file_name}")
        segmentation_res, phase1_usage = self._classify_and_segment(
            file_bytes,
            file_name,
            mime_type,
            extraction_schemas,
            extract_all_documents,
            model_name,
            temperature,
            top_p,
            top_k,
            max_output_tokens,
            thinking_budget,
            thinking_level,
        )
        total_input_tokens += phase1_usage.get("input_tokens", 0)
        total_output_tokens += phase1_usage.get("output_tokens", 0)

        if not isinstance(segmentation_res, dict):
            logger.warning("Phase 1 failed or returned unexpected format. Marking file as invalid.")
            return {"documents": []}

        docs = segmentation_res.get("documents", [])
        if not isinstance(docs, list):
            logger.warning("Phase 1 documents is not a list. Returning empty document list.")
            return {"documents": []}

        if not docs:
            return {"documents": []}

        # Prepare schemas map
        schema_map = {s.document_code: s for s in extraction_schemas}

        def process_doc(doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
            doc_code = doc.get("document_code", "unknown")
            schema = schema_map.get(doc_code)

            is_pdf = mime_type.lower() == "application/pdf"
            start_page = doc.get("start_page", 1)
            end_page = doc.get("end_page", 1)

            chunk_bytes = file_bytes
            if is_pdf:
                chunk_bytes = slice_pdf_multiple_ranges(file_bytes, [(start_page, end_page)])

            logger.info(f"Phase 2: Extracting {doc_code} block (Pages {start_page}-{end_page})")

            # WHY: Upgrade model to gemini-2.5-pro for claim_form documents
            # because they require higher accuracy for complex field extraction
            doc_model = (
                "gemini-2.5-pro"
                if doc_code == "claim_form" and model_name != "gemini-2.5-pro"
                else model_name
            )
            if doc_model == "gemini-2.5-pro" and model_name != "gemini-2.5-pro":
                logger.info(f"Upgrading model to 'gemini-2.5-pro' for {doc_code} in Stage 2")

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

            doc["extracted_data"] = extracted_res if isinstance(extracted_res, dict) else {}
            return doc, phase2_usage

        logger.info(
            f"Phase 2: Starting parallel extraction for {len(docs)} documents "
            f"(max_workers={settings.GEMINI_MAX_CONCURRENT_EXTRACTIONS})"
        )
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.GEMINI_MAX_CONCURRENT_EXTRACTIONS
        ) as executor:
            for _, usage in executor.map(process_doc, docs):
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)

        total_tokens = total_input_tokens + total_output_tokens
        logger.info(
            f"Token Usage (Pipeline Total) - Input: {total_input_tokens:,}, "
            f"Output: {total_output_tokens:,}, Total: {total_tokens:,}"
        )

        return {"documents": docs}
