"""OCR preparation and document audit helpers."""

import asyncio
import json
import mimetypes
import os
from datetime import UTC, datetime

import requests
import structlog
from config import settings
from fastapi import HTTPException
from mongodb_client import get_collection

from services.file_policy import resolve_upload_path

logger = structlog.get_logger(__name__)

OCR_STAGE_V1_DOCUMENT = "v1_document"
OCR_STAGE_PHASE1 = "phase1_classified"
OCR_STAGE_PHASE2 = "phase2_extracted"


def run_ocr_document(file_path: str) -> dict:
    """Run OCR service document extraction for a file path."""
    if _selected_ocr_version() == "v2":
        return run_ocr_v2_classify_segment(file_path)
    return run_ocr_v1_document(file_path)


def run_ocr_v1_document(file_path: str) -> dict:
    """Run OCR service v1 document extraction for a file path."""
    endpoint = f"{settings.OCR_SERVICE_URL}/api/v1/ocr/document"
    resolved_file_path = _resolve_input_file_path(file_path)

    if not os.path.exists(resolved_file_path):
        raise HTTPException(status_code=400, detail=f"Không tìm thấy tệp đầu vào: {file_path}")

    mime_type, _ = mimetypes.guess_type(resolved_file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(resolved_file_path, "rb") as f:
        files = {"file": (os.path.basename(resolved_file_path), f, mime_type)}
        response = requests.post(
            endpoint,
            files=files,
            timeout=_ocr_request_timeout(),  # nosec B113 - centralized OCR timeout.
        )
        response.raise_for_status()
        result = response.json()

    if isinstance(result, dict):
        result = _tag_ocr_version(result, "v1")
        result["ocr_pipeline"] = result.get("ocr_pipeline", "v1")
        result["ocr_stage"] = result.get("ocr_stage", OCR_STAGE_V1_DOCUMENT)
        return result
    return {
        "ocr_version": "v1",
        "ocr_pipeline": "v1",
        "ocr_stage": OCR_STAGE_V1_DOCUMENT,
        "data": result,
    }


def run_ocr_v2_document(file_path: str) -> dict:
    """Run OCR service v2 phase 1 classification for a file path."""
    return run_ocr_v2_classify_segment(file_path)


def run_ocr_v2_classify_segment(file_path: str) -> dict:
    """Run OCR service v2 phase 1 classification and segmentation."""
    endpoint = f"{settings.OCR_SERVICE_URL}/api/v2/ocr/classify-segment/form"
    resolved_file_path = _resolve_input_file_path(file_path)

    if not os.path.exists(resolved_file_path):
        raise HTTPException(status_code=400, detail=f"Không tìm thấy tệp đầu vào: {file_path}")

    mime_type, _ = mimetypes.guess_type(resolved_file_path)
    mime_type = mime_type or "application/octet-stream"

    data: dict[str, str] = {}
    document_codes = _csv_setting(settings.OCR_V2_DOCUMENT_CODES)
    if document_codes:
        data["document_codes"] = json.dumps(document_codes)
    if settings.OCR_V2_MODEL:
        data["model_name"] = settings.OCR_V2_MODEL

    with open(resolved_file_path, "rb") as f:
        files = {"file": (os.path.basename(resolved_file_path), f, mime_type)}
        response = requests.post(
            endpoint,
            files=files,
            data=data,
            timeout=_ocr_request_timeout(),  # nosec B113 - centralized OCR timeout.
        )
        _raise_ocr_for_status(response)
        result = response.json()

    if not isinstance(result, dict):
        return {
            "ocr_version": "v2",
            "ocr_pipeline": settings.OCR_V2_PIPELINE,
            "ocr_stage": OCR_STAGE_PHASE1,
            "documents": [],
            "data": result,
        }
    return _normalize_ocr_v2_result(result, ocr_stage=OCR_STAGE_PHASE1)


def run_ocr_v2_extract(file_path: str, phase1_documents: list[dict]) -> dict:
    """Run OCR service v2 phase 2 extraction for classified documents."""
    endpoint = f"{settings.OCR_SERVICE_URL}/api/v2/ocr/extract/form"
    resolved_file_path = _resolve_input_file_path(file_path)

    if not os.path.exists(resolved_file_path):
        raise HTTPException(status_code=400, detail=f"Không tìm thấy tệp đầu vào: {file_path}")

    mime_type, _ = mimetypes.guess_type(resolved_file_path)
    mime_type = mime_type or "application/octet-stream"

    data: dict[str, str] = {
        "documents": json.dumps(phase1_documents, ensure_ascii=False),
        "extract_all_fields": str(settings.OCR_V2_EXTRACT_ALL_FIELDS).lower(),
    }
    document_codes = _csv_setting(settings.OCR_V2_DOCUMENT_CODES)
    if document_codes:
        data["document_codes"] = json.dumps(document_codes)
    if settings.OCR_V2_MODEL:
        data["model_name"] = settings.OCR_V2_MODEL

    with open(resolved_file_path, "rb") as f:
        files = {"file": (os.path.basename(resolved_file_path), f, mime_type)}
        response = requests.post(
            endpoint,
            files=files,
            data=data,
            timeout=_ocr_request_timeout(),  # nosec B113 - centralized OCR timeout.
        )
        _raise_ocr_for_status(response)
        result = response.json()

    if not isinstance(result, dict):
        return {
            "ocr_version": "v2",
            "ocr_pipeline": settings.OCR_V2_PIPELINE,
            "ocr_stage": OCR_STAGE_PHASE2,
            "documents": [],
            "phase1_documents": phase1_documents,
            "data": result,
        }
    normalized = _normalize_ocr_v2_result(result, ocr_stage=OCR_STAGE_PHASE2)
    normalized["phase1_documents"] = phase1_documents
    return normalized


def _resolve_input_file_path(file_path: str) -> str:
    """Resolve workflow input paths and restrict them to UPLOADS_DIR."""
    return str(resolve_upload_path(file_path))


def save_ocr_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    file_path: str,
    ocr_result: dict,
    file_hash: str | None = None,
    ocr_version: str | None = None,
    ocr_stage: str | None = None,
    cache_status: str = "created",
    source_document_id: str | None = None,
) -> None:
    """Save raw OCR result to MongoDB for auditing and potential reuse."""
    try:
        version = ocr_version or _selected_ocr_version()
        stage = ocr_stage or ocr_result.get("ocr_stage") or _default_ocr_stage(version)
        pipeline = _selected_ocr_pipeline(version)
        doc = {
            "run_id": run_id,
            "claim_id": claim_id,
            "policy_number": policy_number,
            "file_path": file_path,
            "file_hash": file_hash,
            "ocr_version": version,
            "ocr_stage": stage,
            "ocr_pipeline": pipeline,
            "cache_status": cache_status,
            "source_document_id": source_document_id,
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
    ocr_version = _selected_ocr_version()
    ocr_stage = _default_ocr_stage(ocr_version)
    ocr_pipeline = _selected_ocr_pipeline(ocr_version)

    if file_hash:
        collection = get_collection("documents")
        existing_doc = await asyncio.to_thread(
            collection.find_one,
            _cache_query(file_hash, ocr_version, ocr_stage, ocr_pipeline),
        )

        if existing_doc:
            logger.info(
                "Using existing OCR result for hash",
                hash=file_hash,
                version=ocr_version,
                stage=ocr_stage,
            )
            ocr_result = existing_doc.get("ocr_result")
            await asyncio.to_thread(
                save_ocr_result,
                run_id,
                claim_id,
                policy_number,
                input_file,
                ocr_result,
                file_hash,
                ocr_version,
                ocr_stage,
                "reused",
                _document_id(existing_doc),
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
            ocr_version,
            ocr_stage,
            "created",
            None,
        )

    return ocr_result


async def prepare_ocr_phase2_result(
    run_id: str,
    claim_id: str,
    policy_number: str,
    input_file: str,
    phase1_documents: list[dict],
    file_hash: str | None = None,
) -> dict:
    """Load cached OCR v2 phase 2 result or extract classified documents."""
    ocr_result = None
    ocr_version = "v2"
    ocr_stage = OCR_STAGE_PHASE2
    ocr_pipeline = settings.OCR_V2_PIPELINE

    if file_hash:
        collection = get_collection("documents")
        existing_doc = await asyncio.to_thread(
            collection.find_one,
            _cache_query(file_hash, ocr_version, ocr_stage, ocr_pipeline),
        )

        if existing_doc:
            logger.info(
                "Using existing OCR phase 2 result for hash",
                hash=file_hash,
                version=ocr_version,
                stage=ocr_stage,
            )
            ocr_result = existing_doc.get("ocr_result")
            await asyncio.to_thread(
                save_ocr_result,
                run_id,
                claim_id,
                policy_number,
                input_file,
                ocr_result,
                file_hash,
                ocr_version,
                ocr_stage,
                "reused",
                _document_id(existing_doc),
            )

    if not ocr_result:
        ocr_result = await asyncio.to_thread(run_ocr_v2_extract, input_file, phase1_documents)
        await asyncio.to_thread(
            save_ocr_result,
            run_id,
            claim_id,
            policy_number,
            input_file,
            ocr_result,
            file_hash,
            ocr_version,
            ocr_stage,
            "created",
            None,
        )

    return ocr_result


def _selected_ocr_version() -> str:
    version = settings.OCR_API_VERSION.strip().lower()
    if version not in {"v1", "v2"}:
        raise HTTPException(
            status_code=500,
            detail="OCR_API_VERSION chỉ được nhận giá trị 'v1' hoặc 'v2'",
        )
    return version


def _cache_query(file_hash: str, ocr_version: str, ocr_stage: str, ocr_pipeline: str) -> dict:
    return {
        "file_hash": file_hash,
        "ocr_version": ocr_version,
        "ocr_stage": ocr_stage,
        "ocr_pipeline": ocr_pipeline,
        "$or": [
            {"cache_status": {"$exists": False}},
            {"cache_status": "created"},
        ],
    }


def _document_id(document: dict) -> str | None:
    value = document.get("_id")
    if value is None:
        return None
    return str(value)


def _default_ocr_stage(ocr_version: str) -> str:
    if ocr_version == "v2":
        return OCR_STAGE_PHASE1
    return OCR_STAGE_V1_DOCUMENT


def _selected_ocr_pipeline(ocr_version: str) -> str:
    if ocr_version == "v2":
        return settings.OCR_V2_PIPELINE
    return "v1"


def _raise_ocr_for_status(response: requests.Response) -> None:
    if response.ok:
        return

    detail = _ocr_error_detail(response)
    message = str(response)
    if detail:
        message = f"{message} - {detail}"
    raise requests.HTTPError(message, response=response)


def _ocr_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    if isinstance(payload, dict):
        detail = payload.get("detail")
        return str(detail) if detail else response.text.strip()
    return str(payload)


def _csv_setting(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _ocr_request_timeout() -> tuple[int, int]:
    return (settings.OUTBOUND_HTTP_CONNECT_TIMEOUT, settings.OCR_TIMEOUT)


def _tag_ocr_version(result: dict, version: str) -> dict:
    if result.get("ocr_version") == version:
        return result
    return {**result, "ocr_version": version}


def _normalize_ocr_v2_result(result: dict, *, ocr_stage: str) -> dict:
    documents = result.get("documents")
    if not isinstance(documents, list):
        documents = []

    document_codes = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        code = document.get("document_code") or document.get("suggested_document_code")
        if code and code not in document_codes:
            document_codes.append(code)

    return {
        **result,
        "ocr_version": "v2",
        "ocr_pipeline": settings.OCR_V2_PIPELINE,
        "ocr_stage": ocr_stage,
        "documents": documents,
        "document_codes": document_codes,
    }
