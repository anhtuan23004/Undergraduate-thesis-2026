"""OCR phase 2 extraction graph node."""

import structlog
from services.ocr_pipeline import OCR_STAGE_PHASE2, get_default_ocr_pipeline

from graphs.constants import STAGE_FINAL, STAGE_NONE, STAGE_QUALITY, STATUS_RUNNING
from graphs.state import GraphState

logger = structlog.get_logger(__name__)


async def run_ocr_extraction(state: GraphState) -> dict:
    """Extract structured fields after Completeness Agent approves Phase 1."""
    logger.info("Executing OCR extraction node", claim_id=state.get("claim_id"))
    extracted_docs = state.get("extracted_documents", {})
    pipeline = get_default_ocr_pipeline()
    phase1_documents = pipeline.phase2_input_documents(extracted_docs)

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
