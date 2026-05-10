"""OCR preparation and document audit helpers."""

import asyncio
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path

import requests
import structlog
from config import settings
from fastapi import HTTPException
from mongodb_client import get_collection

logger = structlog.get_logger(__name__)


def run_ocr_document(file_path: str) -> dict:
    """Run OCR service document extraction for a file path."""
    endpoint = f"{settings.OCR_SERVICE_URL}/api/v1/ocr/document"
    resolved_file_path = _resolve_input_file_path(file_path)

    if not os.path.exists(resolved_file_path):
        raise HTTPException(status_code=400, detail=f"Input file not found: {file_path}")

    mime_type, _ = mimetypes.guess_type(resolved_file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(resolved_file_path, "rb") as f:
        files = {"file": (os.path.basename(resolved_file_path), f, mime_type)}
        response = requests.post(endpoint, files=files, timeout=settings.OCR_TIMEOUT)
        response.raise_for_status()
        result = response.json()

    if isinstance(result, dict):
        return result
    return {"data": result}


def _resolve_input_file_path(file_path: str) -> str:
    """Resolve workflow input paths and restrict them to UPLOADS_DIR."""
    upload_dir = Path(settings.UPLOADS_DIR).expanduser().resolve()
    candidate = Path(file_path).expanduser()
    resolved = (
        candidate.resolve() if candidate.is_absolute() else (upload_dir / candidate).resolve()
    )

    if resolved != upload_dir and upload_dir not in resolved.parents:
        raise HTTPException(
            status_code=400,
            detail="Input file must be inside UPLOADS_DIR",
        )

    return str(resolved)


def save_ocr_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    file_path: str,
    ocr_result: dict,
    file_hash: str | None = None,
) -> None:
    """Save raw OCR result to MongoDB for auditing and potential reuse."""
    try:
        doc = {
            "run_id": run_id,
            "claim_id": claim_id,
            "policy_number": policy_number,
            "file_path": file_path,
            "file_hash": file_hash,
            "ocr_result": ocr_result,
            "created_at": datetime.now(UTC),
        }
        collection = get_collection("documents")
        collection.insert_one(doc)
    except Exception as exc:
        logger.error("Failed to save OCR result", error=str(exc))


async def prepare_ocr_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    input_file: str,
    file_hash: str | None = None,
) -> dict:
    """Load cached OCR by hash or call OCR service, then audit the result."""
    ocr_result = None

    if file_hash:
        collection = get_collection("documents")
        existing_doc = await asyncio.to_thread(collection.find_one, {"file_hash": file_hash})

        if existing_doc:
            logger.info("Using existing OCR result for hash", hash=file_hash)
            ocr_result = existing_doc.get("ocr_result")
            await asyncio.to_thread(
                save_ocr_result,
                run_id,
                claim_id,
                policy_number,
                input_file,
                ocr_result,
                file_hash,
            )

    if not ocr_result:
        ocr_result = await asyncio.to_thread(run_ocr_document, input_file)
        await asyncio.to_thread(
            save_ocr_result,
            run_id,
            claim_id,
            policy_number,
            input_file,
            ocr_result,
            file_hash,
        )

    return ocr_result
