"""OCR phase 2 extraction graph node."""

from collections.abc import Callable
from typing import Any

import structlog
from workflow.contracts import (
    OCR_STAGE_PHASE2_EXTRACTED,
    STAGE_FINAL,
    STAGE_NONE,
    STAGE_QUALITY,
    STATUS_RUNNING,
    GraphState,
)

logger = structlog.get_logger(__name__)

_CLASSIFICATION_KEYS = (
    "document_code",
    "document_name",
    "suggested_document_code",
    "suggested_document_name",
    "start_page",
    "end_page",
    "page_ranges",
    "page_order",
    "duplicate_pages",
)


def get_default_ocr_pipeline() -> Any:
    """Return the configured OCR pipeline provider.

    Production injects the provider when compiling the graph. Tests may
    monkeypatch this compatibility function directly.
    """
    raise RuntimeError("OCR pipeline provider has not been configured")


def create_ocr_extraction_node(pipeline_provider: Callable[[], Any]) -> Callable:
    """Create an OCR extraction node bound to a concrete OCR pipeline provider."""

    async def ocr_extraction_node(state: GraphState) -> dict:
        return await _run_ocr_extraction(state, pipeline_provider())

    return ocr_extraction_node


async def run_ocr_extraction(state: GraphState) -> dict:
    """Extract structured fields after Completeness Agent approves Phase 1."""
    try:
        pipeline = get_default_ocr_pipeline()
    except RuntimeError:
        pipeline = None
    return await _run_ocr_extraction(state, pipeline)


async def _run_ocr_extraction(state: GraphState, pipeline: Any) -> dict:
    """Extract structured fields with an injected OCR pipeline."""
    logger.info("Executing OCR extraction node", claim_id=state.get("claim_id"))
    extracted_docs = state.get("extracted_documents", {})
    phase1_documents = _phase2_input_documents(extracted_docs, pipeline)

    try:
        if not phase1_documents:
            raise ValueError(
                "Cần có danh sách chứng từ từ OCR giai đoạn 1 trước khi trích xuất giai đoạn 2"
            )

        phase2_result = await pipeline.prepare_phase2_ocr(
            state["run_id"],
            state["claim_id"],
            state["policy_number"],
            state["input_file"],
            phase1_documents,
            state.get("file_hash"),
        )

        return {
            "extracted_documents": phase2_result,
            "ocr_stage": OCR_STAGE_PHASE2_EXTRACTED,
            "history": [
                {
                    "step": "ocr_extraction",
                    "agent": "System",
                    "status": "success",
                    "documents": len(phase2_result.get("documents", [])),
                }
            ],
            "current_step": "completed_ocr_extraction",
            "active_stage": STAGE_QUALITY,
            "review_stage": STAGE_NONE,
            "workflow_status": STATUS_RUNNING,
        }
    except Exception as exc:
        logger.error("OCR phase 2 extraction failed", error=str(exc))
        failed_documents = {
            **extracted_docs,
            "ocr_stage": "error",
            "error": {
                "stage": "phase2_extraction",
                "code": "OCR_EXTRACTION_FAILED",
                "message": str(exc),
            },
        }
        return {
            "extracted_documents": failed_documents,
            "agent_2_result": {
                "valid": False,
                "decision": "reject",
                "issues": [
                    {
                        "severity": "high",
                        "code": "OCR_EXTRACTION_FAILED",
                        "description": "Không thể trích xuất dữ liệu chi tiết từ hồ sơ.",
                        "reason": str(exc),
                    }
                ],
                "message": "Không thể chạy OCR giai đoạn 2 sau bước kiểm tra tính đầy đủ.",
                "confidence_score": 1.0,
                "evidence": {"ocr_stage": "error"},
            },
            "ocr_stage": "error",
            "history": [
                {
                    "step": "ocr_extraction",
                    "agent": "System",
                    "status": "error",
                    "error": str(exc),
                }
            ],
            "current_step": "failed_ocr_extraction",
            "active_stage": STAGE_FINAL,
            "review_stage": STAGE_NONE,
            "workflow_status": STATUS_RUNNING,
        }


def _phase2_input_documents(extracted_documents: dict, pipeline: Any) -> list[dict]:
    if hasattr(pipeline, "phase2_input_documents"):
        return pipeline.phase2_input_documents(extracted_documents)
    return [
        {key: doc[key] for key in _CLASSIFICATION_KEYS if key in doc}
        for doc in extracted_documents.get("documents", [])
        if isinstance(doc, dict)
    ]
