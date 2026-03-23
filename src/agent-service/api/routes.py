"""Workflow API routes using LangGraph workflow with MongoDB persistence."""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List
from pathlib import Path
import mimetypes
import hashlib
import structlog

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
import requests

from config import settings
from graphs import build_claim_workflow
from graphs.state import GraphState
from mongodb_client import get_collection

from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

router = APIRouter(prefix="/api/v1", tags=["workflows"])

_compiled_graph = None
_mongo_checkpointer = None
logger = structlog.get_logger(__name__)


async def _get_mongo_checkpointer() -> Any:
    """Get or create MongoDB checkpointer using pymongo driver.

    Returns:
        Any: The MongoDB checkpointer for LangGraph.
    """
    global _mongo_checkpointer
    if _mongo_checkpointer is None:
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        mongo_url = settings.MONGODB_URL
        if "directConnection" not in mongo_url:
            separator = "&" if "?" in mongo_url else "?"
            mongo_url += f"{separator}directConnection=true"

        client = MongoClient(mongo_url)
        _mongo_checkpointer = MongoDBSaver(client, db_name=settings.MONGODB_DB)
    return _mongo_checkpointer


async def _get_graph() -> Any:
    """Get or create the compiled workflow graph."""
    global _compiled_graph
    if _compiled_graph is None:
        from agent import get_llm_client

        checkpointer = await _get_mongo_checkpointer()
        _compiled_graph = build_claim_workflow(
            llm_client=get_llm_client(),
            checkpointer=checkpointer,
        )
    return _compiled_graph


class ClaimRequest(BaseModel):
    """Request model for claim processing."""

    claim_id: str = Field(..., description="Claim identifier")
    policy_number: str = Field(..., description="Policy number")
    input_file: str = Field(..., description="Path to input document")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of the document")


class HumanReviewRequest(BaseModel):
    """Request model for human review decision."""

    decision: str = Field(..., description="Decision: approve, reject, or edit")
    notes: Optional[str] = Field(default=None, description="Reviewer notes")
    edited_result: Optional[dict] = Field(
        default=None, description="Edited agent result if decision is edit"
    )


class ContinueRequest(BaseModel):
    """Request model for continuing a paused workflow stage."""

    note: Optional[str] = Field(default=None, description="Optional note for audit trail")


class UploadResponse(BaseModel):
    """Response model for uploaded documents."""

    filename: str
    file_path: str
    size_bytes: int
    file_hash: str


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
        from mongodb_client import get_collection

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


@router.post("/workflows/upload", response_model=UploadResponse)
async def upload_workflow_document(file: UploadFile = File(...)) -> UploadResponse:
    """Upload a claim document and return server-side path for workflow usage.

    Args:
        file: The uploaded file from the client.

    Returns:
        UploadResponse: Details of the uploaded file including its saved path.

    Raises:
        HTTPException: If the file fails to save.
    """
    try:
        upload_dir = Path(settings.UPLOADS_DIR).expanduser().resolve()
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(file.filename or "claim_document").name
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        output_path = upload_dir / unique_name

        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Enforce file size limit
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB}MB"
            )

        output_path.write_bytes(content)

        return UploadResponse(
            filename=safe_name,
            file_path=str(output_path),
            size_bytes=len(content),
            file_hash=file_hash,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")


@router.post("/workflows/run")
async def run_workflow(request: ClaimRequest) -> dict:
    """Start a new claim processing workflow."""
    graph = await _get_graph()
    run_id = str(uuid.uuid4())
    ocr_result = None

    try:
        # Deduplication: Check for existing OCR result if file_hash is provided
        if request.file_hash:
            from mongodb_client import get_collection
            # Use synchronous find_one since get_collection uses pymongo (sync)
            collection = get_collection("documents")
            existing_doc = await asyncio.to_thread(
                collection.find_one, {"file_hash": request.file_hash}
            )

            if existing_doc:
                logger.info("Using existing OCR result for hash", hash=request.file_hash)
                ocr_result = existing_doc.get("ocr_result")

                # Persist a new document record for this run, reusing the existing OCR result
                await asyncio.to_thread(
                    _save_ocr_result,
                    run_id,
                    request.claim_id,
                    request.policy_number,
                    request.input_file,
                    ocr_result,
                    request.file_hash,
                )

        # If not found or no hash provided, run OCR service
        if not ocr_result:
            ocr_result = await asyncio.to_thread(_run_ocr_document, request.input_file)
            await asyncio.to_thread(
                _save_ocr_result,
                run_id,
                request.claim_id,
                request.policy_number,
                request.input_file,
                ocr_result,
                request.file_hash,
            )
    except requests.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"OCR service returned error: {e.response.status_code if e.response else str(e)}",
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect OCR service: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare OCR data: {str(e)}")

    initial_state: GraphState = {
        "run_id": run_id,
        "claim_id": request.claim_id,
        "policy_number": request.policy_number,
        "input_file": request.input_file,
        "extracted_documents": ocr_result,
        "agent_1_result": None,
        "agent_2_result": None,
        "human_review_result": None,
        "edited_agent_1_result": None,
        "edited_agent_2_result": None,
        "final_result": None,
        "history": [],
        "current_step": "start",
        "should_continue": True,
        "error": None,
        "pending_human_review": False,
    }

    try:
        async with asyncio.timeout(settings.PROCESS_TIMEOUT):
            config = {"configurable": {"thread_id": run_id}}
            result = await graph.ainvoke(initial_state, config=config)

            snapshot = await graph.aget_state(config)
            is_pending, is_paused, pause_at = _extract_pause_state(snapshot)

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Processing timed out after {settings.PROCESS_TIMEOUT}s",
        )

    return {
        "run_id": run_id,
        "claim_id": result.get("claim_id"),
        "extracted_documents": result.get("extracted_documents"),
        "final_result": result.get("final_result"),
        "agent_1_result": result.get("agent_1_result"),
        "agent_2_result": result.get("agent_2_result"),
        "current_step": result.get("current_step"),
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "history": result.get("history", []),
        "error": result.get("error"),
    }


@router.post("/workflows/resume/{run_id}")
async def resume_workflow(run_id: str, request: HumanReviewRequest) -> dict:
    """Resume a workflow after human review decision.

    Args:
        run_id: The unique identifier of the workflow.
        request: The human review decision payload.

    Returns:
        dict: The updated state of the workflow graph.

    Raises:
        HTTPException: If the workflow run is not found or times out.
    """
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    async with asyncio.timeout(settings.PROCESS_TIMEOUT):
        current_state = await graph.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        state_values = current_state.values
        stage = _determine_review_stage(state_values)

        human_review_result = {
            "decision": request.decision,
            "notes": request.notes,
            "stage": stage,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

        state_update = {
            "human_review_result": human_review_result,
            "current_step": "human_review_complete",
            "history": [
                {
                    "step": "human_review",
                    "decision": request.decision,
                    "notes": request.notes,
                    "resumed": True,
                }
            ],
        }

        if request.decision == "edit" and request.edited_result:
            if stage == "completeness":
                state_update["edited_agent_1_result"] = request.edited_result
            else:
                state_update["edited_agent_2_result"] = request.edited_result

        await graph.aupdate_state(config, state_update, as_node="human_review")
        result = await graph.ainvoke(None, config=config)

        snapshot = await graph.aget_state(config)
        is_pending, is_paused, pause_at = _extract_pause_state(snapshot)

    return {
        "run_id": run_id,
        "claim_id": result.get("claim_id"),
        "extracted_documents": result.get("extracted_documents"),
        "final_result": result.get("final_result"),
        "agent_1_result": result.get("agent_1_result"),
        "agent_2_result": result.get("agent_2_result"),
        "current_step": result.get("current_step"),
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "history": result.get("history", []),
        "error": result.get("error"),
    }


@router.post("/workflows/continue/{run_id}")
async def continue_workflow(run_id: str, request: ContinueRequest | None = None) -> dict:
    """Continue a workflow paused at a non-human stage.

    Args:
        run_id: The unique identifier of the workflow.
        request: Optional continuation note.

    Returns:
        dict: The updated state of the workflow graph.

    Raises:
        HTTPException: If workflow run not found, timed out, or requires human review.
    """
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    async with asyncio.timeout(settings.PROCESS_TIMEOUT):
        current_state = await graph.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        if current_state.next and "human_review" in current_state.next:
            raise HTTPException(
                status_code=400,
                detail="Workflow is waiting for human review. Use /workflows/resume/{run_id}.",
            )

        # Optional audit marker for manual continuation in UI.
        if request and request.note:
            await graph.aupdate_state(
                config,
                {
                    "history": [
                        {
                            "step": "manual_continue",
                            "note": request.note,
                        }
                    ]
                },
            )

        result = await graph.ainvoke(None, config=config)
        snapshot = await graph.aget_state(config)
        is_pending, is_paused, pause_at = _extract_pause_state(snapshot)

    return {
        "run_id": run_id,
        "claim_id": result.get("claim_id"),
        "extracted_documents": result.get("extracted_documents"),
        "final_result": result.get("final_result"),
        "agent_1_result": result.get("agent_1_result"),
        "agent_2_result": result.get("agent_2_result"),
        "current_step": result.get("current_step"),
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "history": result.get("history", []),
        "error": result.get("error"),
    }


def _determine_review_stage(state: dict) -> str:
    """Determine which stage the human review is for based on the current step."""
    current_step = state.get("current_step", "")
    if "quality" in current_step:
        return "quality"
    return "completeness"


@router.get("/workflows/status/{run_id}")
async def get_workflow_status(run_id: str) -> dict:
    """Get the current status of a workflow run."""
    graph = await _get_graph()
    config = {"configurable": {"thread_id": run_id}}

    state = await graph.aget_state(config)

    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    values = state.values
    is_pending, is_paused, pause_at = _extract_pause_state(state)

    return {
        "run_id": run_id,
        "claim_id": values.get("claim_id"),
        "extracted_documents": values.get("extracted_documents"),
        "current_step": values.get("current_step"),
        "pending_human_review": is_pending,
        "paused": is_paused,
        "pause_at": pause_at,
        "agent_1_result": values.get("agent_1_result"),
        "agent_2_result": values.get("agent_2_result"),
        "human_review_result": values.get("human_review_result"),
        "final_result": values.get("final_result"),
        "history": values.get("history", []),
        "error": values.get("error"),
    }


@router.get("/health")
async def health_check() -> dict:
    """Simple health check endpoint.

    Returns:
        dict: API health status and application version.
    """
    return {"status": "healthy", "version": settings.APP_VERSION}
