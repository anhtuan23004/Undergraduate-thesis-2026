"""OCR pipeline orchestration and OCR Service adapter."""

import asyncio
import hashlib
import json
import mimetypes
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

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


@dataclass(frozen=True)
class OcrOperationSpec:
    """OCR operation fields that affect service behavior and cache identity."""

    version: str
    stage: str
    pipeline: str
    model_name: str = ""
    document_codes: tuple[str, ...] = ()
    extract_all_fields: bool | None = None
    source_documents_fingerprint: str | None = None

    def fingerprint(self) -> str:
        payload = {
            "document_codes": list(self.document_codes),
            "extract_all_fields": self.extract_all_fields,
            "model_name": self.model_name,
            "pipeline": self.pipeline,
            "source_documents_fingerprint": self.source_documents_fingerprint,
            "stage": self.stage,
            "version": self.version,
        }
        return stable_fingerprint(payload)


@dataclass(frozen=True)
class OcrCacheIdentity:
    """Stable identity for an OCR cache entry."""

    file_hash: str
    operation: OcrOperationSpec

    @property
    def fingerprint(self) -> str:
        return self.operation.fingerprint()


@dataclass(frozen=True)
class OcrWorkflowContext:
    """Workflow metadata needed by OCR orchestration and audit."""

    run_id: str
    claim_id: str
    policy_number: str
    input_file: str
    file_hash: str | None = None

    def cache_identity(self, operation: OcrOperationSpec) -> OcrCacheIdentity | None:
        if not self.file_hash:
            return None
        return OcrCacheIdentity(file_hash=self.file_hash, operation=operation)


class OcrAdapter(Protocol):
    """Boundary for calls to the external OCR Service."""

    def run_document(self, file_path: str) -> dict:
        """Run the configured initial OCR operation."""

    def run_phase2_extract(self, file_path: str, phase1_documents: list[dict]) -> dict:
        """Run v2 field extraction using phase 1 classification metadata."""


class OcrServiceAdapter:
    """HTTP multipart adapter for the OCR Service."""

    def run_document(self, file_path: str) -> dict:
        """Run OCR service document extraction for a file path."""
        if selected_ocr_version() == "v2":
            return self.run_v2_classify_segment(file_path)
        return self.run_v1_document(file_path)

    def run_v1_document(self, file_path: str) -> dict:
        """Run OCR service v1 document extraction for a file path."""
        endpoint = f"{settings.OCR_SERVICE_URL}/api/v1/ocr/document"
        resolved_file_path = resolve_input_file_path(file_path)

        if not os.path.exists(resolved_file_path):
            raise HTTPException(status_code=400, detail=f"Không tìm thấy tệp đầu vào: {file_path}")

        mime_type, _ = mimetypes.guess_type(resolved_file_path)
        mime_type = mime_type or "application/octet-stream"

        with open(resolved_file_path, "rb") as f:
            files = {"file": (os.path.basename(resolved_file_path), f, mime_type)}
            response = requests.post(
                endpoint,
                files=files,
                timeout=ocr_request_timeout(),  # nosec B113 - centralized OCR timeout.
            )
            response.raise_for_status()
            result = response.json()

        if isinstance(result, dict):
            result = tag_ocr_version(result, "v1")
            result["ocr_pipeline"] = result.get("ocr_pipeline", "v1")
            result["ocr_stage"] = result.get("ocr_stage", OCR_STAGE_V1_DOCUMENT)
            return result
        return {
            "ocr_version": "v1",
            "ocr_pipeline": "v1",
            "ocr_stage": OCR_STAGE_V1_DOCUMENT,
            "data": result,
        }

    def run_v2_document(self, file_path: str) -> dict:
        """Run OCR service v2 phase 1 classification for a file path."""
        return self.run_v2_classify_segment(file_path)

    def run_v2_classify_segment(self, file_path: str) -> dict:
        """Run OCR service v2 phase 1 classification and segmentation."""
        endpoint = f"{settings.OCR_SERVICE_URL}/api/v2/ocr/classify-segment/form"
        resolved_file_path = resolve_input_file_path(file_path)

        if not os.path.exists(resolved_file_path):
            raise HTTPException(status_code=400, detail=f"Không tìm thấy tệp đầu vào: {file_path}")

        mime_type, _ = mimetypes.guess_type(resolved_file_path)
        mime_type = mime_type or "application/octet-stream"

        data: dict[str, str] = {}
        document_codes = csv_setting(settings.OCR_V2_DOCUMENT_CODES)
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
                timeout=ocr_request_timeout(),  # nosec B113 - centralized OCR timeout.
            )
            raise_ocr_for_status(response)
            result = response.json()

        if not isinstance(result, dict):
            return {
                "ocr_version": "v2",
                "ocr_pipeline": settings.OCR_V2_PIPELINE,
                "ocr_stage": OCR_STAGE_PHASE1,
                "documents": [],
                "data": result,
            }
        return normalize_ocr_v2_result(result, ocr_stage=OCR_STAGE_PHASE1)

    def run_phase2_extract(self, file_path: str, phase1_documents: list[dict]) -> dict:
        """Run OCR service v2 phase 2 extraction for classified documents."""
        endpoint = f"{settings.OCR_SERVICE_URL}/api/v2/ocr/extract/form"
        resolved_file_path = resolve_input_file_path(file_path)

        if not os.path.exists(resolved_file_path):
            raise HTTPException(status_code=400, detail=f"Không tìm thấy tệp đầu vào: {file_path}")

        mime_type, _ = mimetypes.guess_type(resolved_file_path)
        mime_type = mime_type or "application/octet-stream"

        data: dict[str, str] = {
            "documents": json.dumps(phase1_documents, ensure_ascii=False),
            "extract_all_fields": str(settings.OCR_V2_EXTRACT_ALL_FIELDS).lower(),
        }
        document_codes = csv_setting(settings.OCR_V2_DOCUMENT_CODES)
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
                timeout=ocr_request_timeout(),  # nosec B113 - centralized OCR timeout.
            )
            raise_ocr_for_status(response)
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
        normalized = normalize_ocr_v2_result(result, ocr_stage=OCR_STAGE_PHASE2)
        normalized["phase1_documents"] = phase1_documents
        return normalized


class OcrPipeline:
    """Owns OCR cache lookup, service execution, audit save, and normalization."""

    def __init__(
        self,
        *,
        adapter: OcrAdapter | None = None,
        collection_provider: Callable[[str], object] = get_collection,
        audit_writer: Callable[..., None] | None = None,
    ) -> None:
        self.adapter = adapter or OcrServiceAdapter()
        self.collection_provider = collection_provider
        self.audit_writer = audit_writer or save_ocr_result

    async def prepare_initial_ocr(
        self,
        run_id: str,
        claim_id: str,
        policy_number: str,
        input_file: str,
        file_hash: str | None = None,
    ) -> dict:
        """Load cached initial OCR by hash or call OCR Service, then audit."""
        context = OcrWorkflowContext(run_id, claim_id, policy_number, input_file, file_hash)
        operation = initial_operation_spec()
        cache_identity = context.cache_identity(operation)
        cached_doc = await self._find_cached_result(cache_identity)

        if cached_doc:
            logger.info(
                "Using existing OCR result for hash",
                hash=context.file_hash,
                version=operation.version,
                stage=operation.stage,
            )
            ocr_result = cached_doc.get("ocr_result")
            await self._save_audit(
                context,
                ocr_result,
                operation,
                "reused",
                document_id(cached_doc),
            )
            return ocr_result

        ocr_result = await asyncio.to_thread(self.adapter.run_document, context.input_file)
        await self._save_audit(
            context,
            ocr_result,
            operation,
            "created",
            None,
        )
        return ocr_result

    async def prepare_phase2_ocr(
        self,
        run_id: str,
        claim_id: str,
        policy_number: str,
        input_file: str,
        phase1_documents: list[dict],
        file_hash: str | None = None,
    ) -> dict:
        """Load cached OCR v2 phase 2 result or extract classified documents."""
        context = OcrWorkflowContext(run_id, claim_id, policy_number, input_file, file_hash)
        operation = phase2_operation_spec(phase1_documents)
        cache_identity = context.cache_identity(operation)
        cached_doc = await self._find_cached_result(cache_identity)

        if cached_doc:
            logger.info(
                "Using existing OCR phase 2 result for hash",
                hash=context.file_hash,
                version=operation.version,
                stage=operation.stage,
            )
            ocr_result = cached_doc.get("ocr_result")
            await self._save_audit(
                context,
                ocr_result,
                operation,
                "reused",
                document_id(cached_doc),
            )
            return ocr_result

        ocr_result = await asyncio.to_thread(
            self.adapter.run_phase2_extract,
            context.input_file,
            phase1_documents,
        )
        await self._save_audit(
            context,
            ocr_result,
            operation,
            "created",
            None,
        )
        return ocr_result

    def phase2_input_documents(self, extracted_documents: dict) -> list[dict]:
        """Return classification-only metadata required by OCR phase 2."""
        return [
            {key: doc[key] for key in _CLASSIFICATION_KEYS if key in doc}
            for doc in extracted_documents.get("documents", [])
            if isinstance(doc, dict)
        ]

    async def _find_cached_result(
        self,
        cache_identity: OcrCacheIdentity | None,
    ) -> dict | None:
        if cache_identity is None:
            return None
        collection = self.collection_provider("documents")
        return await asyncio.to_thread(
            collection.find_one,
            cache_query(cache_identity),
        )

    async def _save_audit(
        self,
        context: OcrWorkflowContext,
        ocr_result: dict,
        operation: OcrOperationSpec,
        cache_status: str,
        source_document_id: str | None,
    ) -> None:
        await asyncio.to_thread(
            self.audit_writer,
            context.run_id,
            context.claim_id,
            context.policy_number,
            context.input_file,
            ocr_result,
            context.file_hash,
            operation.version,
            operation.stage,
            cache_status,
            source_document_id,
            operation=operation,
            cache_identity=context.cache_identity(operation),
        )


def get_default_ocr_pipeline() -> OcrPipeline:
    """Build the production OCR pipeline."""
    return OcrPipeline()


def resolve_input_file_path(file_path: str) -> str:
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
    *,
    operation: OcrOperationSpec | None = None,
    cache_identity: OcrCacheIdentity | None = None,
) -> None:
    """Save raw OCR result to MongoDB for auditing and potential reuse."""
    try:
        version = ocr_version or (operation.version if operation else selected_ocr_version())
        stage = (
            ocr_stage
            or (operation.stage if operation else None)
            or ocr_result.get("ocr_stage")
            or default_ocr_stage(version)
        )
        pipeline = operation.pipeline if operation else selected_ocr_pipeline(version)
        doc = {
            "run_id": run_id,
            "claim_id": claim_id,
            "policy_number": policy_number,
            "file_path": file_path,
            "file_hash": file_hash,
            "ocr_version": version,
            "ocr_stage": stage,
            "ocr_pipeline": pipeline,
            "ocr_model": operation.model_name if operation else "",
            "document_codes": list(operation.document_codes) if operation else [],
            "extract_all_fields": operation.extract_all_fields if operation else None,
            "source_documents_fingerprint": (
                operation.source_documents_fingerprint if operation else None
            ),
            "cache_identity": cache_identity.fingerprint if cache_identity else None,
            "cache_status": cache_status,
            "source_document_id": source_document_id,
            "ocr_result": ocr_result,
            "created_at": datetime.now(UTC),
        }
        collection = get_collection("documents")
        collection.insert_one(doc)
    except Exception as exc:
        logger.error("Failed to save OCR result", error=str(exc))


def initial_operation_spec() -> OcrOperationSpec:
    version = selected_ocr_version()
    return OcrOperationSpec(
        version=version,
        stage=default_ocr_stage(version),
        pipeline=selected_ocr_pipeline(version),
        model_name=settings.OCR_V2_MODEL if version == "v2" else "",
        document_codes=tuple(csv_setting(settings.OCR_V2_DOCUMENT_CODES))
        if version == "v2"
        else (),
    )


def phase2_operation_spec(phase1_documents: list[dict]) -> OcrOperationSpec:
    return OcrOperationSpec(
        version="v2",
        stage=OCR_STAGE_PHASE2,
        pipeline=settings.OCR_V2_PIPELINE,
        model_name=settings.OCR_V2_MODEL,
        document_codes=tuple(csv_setting(settings.OCR_V2_DOCUMENT_CODES)),
        extract_all_fields=settings.OCR_V2_EXTRACT_ALL_FIELDS,
        source_documents_fingerprint=stable_fingerprint(phase1_documents),
    )


def selected_ocr_version() -> str:
    version = settings.OCR_API_VERSION.strip().lower()
    if version not in {"v1", "v2"}:
        raise HTTPException(
            status_code=500,
            detail="OCR_API_VERSION chỉ được nhận giá trị 'v1' hoặc 'v2'",
        )
    return version


def cache_query(cache_identity: OcrCacheIdentity) -> dict:
    return {
        "file_hash": cache_identity.file_hash,
        "ocr_version": cache_identity.operation.version,
        "ocr_stage": cache_identity.operation.stage,
        "ocr_pipeline": cache_identity.operation.pipeline,
        "cache_identity": cache_identity.fingerprint,
        "$or": [
            {"cache_status": {"$exists": False}},
            {"cache_status": "created"},
        ],
    }


def document_id(document: dict) -> str | None:
    value = document.get("_id")
    if value is None:
        return None
    return str(value)


def default_ocr_stage(ocr_version: str) -> str:
    if ocr_version == "v2":
        return OCR_STAGE_PHASE1
    return OCR_STAGE_V1_DOCUMENT


def selected_ocr_pipeline(ocr_version: str) -> str:
    if ocr_version == "v2":
        return settings.OCR_V2_PIPELINE
    return "v1"


def raise_ocr_for_status(response: requests.Response) -> None:
    if response.ok:
        return

    detail = ocr_error_detail(response)
    message = str(response)
    if detail:
        message = f"{message} - {detail}"
    raise requests.HTTPError(message, response=response)


def ocr_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    if isinstance(payload, dict):
        detail = payload.get("detail")
        return str(detail) if detail else response.text.strip()
    return str(payload)


def csv_setting(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def ocr_request_timeout() -> tuple[int, int]:
    return (settings.OUTBOUND_HTTP_CONNECT_TIMEOUT, settings.OCR_TIMEOUT)


def stable_fingerprint(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def tag_ocr_version(result: dict, version: str) -> dict:
    if result.get("ocr_version") == version:
        return result
    return {**result, "ocr_version": version}


def normalize_ocr_v2_result(result: dict, *, ocr_stage: str) -> dict:
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
