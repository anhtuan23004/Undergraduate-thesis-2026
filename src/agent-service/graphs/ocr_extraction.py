"""OCR phase 2 extraction graph node."""

import structlog
from services.ocr_service import OCR_STAGE_PHASE2, prepare_ocr_phase2_result

from graphs.constants import STAGE_FINAL, STAGE_NONE, STAGE_QUALITY, STATUS_RUNNING
from graphs.state import GraphState

logger = structlog.get_logger(__name__)

# WHY: Phase 1 `documents` and Phase 2 `documents` share the same key but
# Phase 2 adds `extracted_data`.  We strip to classification-only fields so
# the Phase 2 API receives a clean input without residual extraction data.
_CLASSIFICATION_KEYS = (
    "document_code",
    "document_name",
    "suggested_document_code",
    "suggested_document_name",
    "start_page",
    "end_page",
)


async def run_ocr_extraction(state: GraphState) -> dict:
    """Extract structured fields after Completeness Agent approves Phase 1."""
    logger.info("Executing OCR extraction node", claim_id=state.get("claim_id"))
    extracted_docs = state.get("extracted_documents", {})
    # Derive phase1_documents from documents, keeping only classification metadata
    phase1_documents = [
        {k: doc[k] for k in _CLASSIFICATION_KEYS if k in doc}
        for doc in extracted_docs.get("documents", [])
        if isinstance(doc, dict)
    ]

    try:
        if not phase1_documents:
            raise ValueError("OCR phase 1 documents are required before phase 2 extraction")

        phase2_result = await prepare_ocr_phase2_result(
            state["run_id"],
            state["claim_id"],
            state["policy_number"],
            state["input_file"],
            phase1_documents,
            state.get("file_hash"),
        )

        return {
            "extracted_documents": phase2_result,
            "ocr_stage": OCR_STAGE_PHASE2,
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
        return {
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
                "message": "Không thể chạy OCR Phase 2 sau bước kiểm tra tính đầy đủ.",
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
