"""Helper functions for workflow routes."""

import hashlib
import mimetypes
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests
import structlog

from config import settings
from mongodb_client import get_collection

logger = structlog.get_logger(__name__)


def _extract_pause_state(snapshot: Any) -> tuple[bool, bool, Optional[str]]:
    """Compute pause flags from graph snapshot.

    Returns:
        pending_human_review, paused, pause_at
    """
    next_nodes = list(snapshot.next or [])
    if not next_nodes:
        return False, False, None

    if "human_review" in next_nodes:
        return True, True, "human_review"

    return False, True, next_nodes[0]


def _run_ocr_document(file_path: str) -> dict:
    """Run OCR service document extraction for a file path.

    Args:
        file_path: Absolute path to the document file.

    Returns:
        dict: The OCR extraction result.

    Raises:
        HTTPException: If file is not found or OCR service fails.
    """
    from fastapi import HTTPException

    endpoint = f"{settings.OCR_SERVICE_URL}/api/v1/ocr/document"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail=f"Input file not found: {file_path}")

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, mime_type)}
        response = requests.post(endpoint, files=files, timeout=settings.OCR_TIMEOUT)
        response.raise_for_status()
        result = response.json()

    if isinstance(result, dict):
        return result
    return {"data": result}


def _save_ocr_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    file_path: str,
    ocr_result: dict,
    file_hash: Optional[str] = None,
) -> None:
    """Save raw OCR result to MongoDB for auditing and potential reuse.

    Args:
        run_id: Unique workflow execution ID.
        claim_id: User-provided claim ID.
        policy_number: Associated policy number.
        file_path: Path to the uploaded document.
        ocr_result: The extracted text/data from OCR.
        file_hash: SHA-256 fingerprint of the document.
    """
    try:
        doc = {
            "run_id": run_id,
            "claim_id": claim_id,
            "policy_number": policy_number,
            "file_path": file_path,
            "file_hash": file_hash,
            "ocr_result": ocr_result,
            "created_at": datetime.now(timezone.utc),
        }
        collection = get_collection("documents")
        collection.insert_one(doc)
    except Exception as e:
        logger.error("Failed to save OCR result", error=str(e))


def _determine_review_stage(state: dict) -> str:
    """Determine which stage the human review is for based on current state.

    Priority order:
    1. If final_result already exists → this is the final approval step
    2. If agent_2_result exists but no final_result → quality stage
    3. Otherwise → completeness stage
    """
    # WHY: Checking state presence is more reliable than parsing current_step strings,
    # because current_step can be any value at the point of human review.
    if state.get("final_result"):
        return "final"
    if state.get("agent_2_result"):
        return "quality"
    return "completeness"


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content.

    Args:
        content: File content as bytes.

    Returns:
        Hex string of SHA-256 hash.
    """
    return hashlib.sha256(content).hexdigest()
