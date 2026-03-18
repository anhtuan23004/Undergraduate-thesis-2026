"""Workflow API routes (src2-integrated runtime)."""

import asyncio
import json
import uuid
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent import run_agent

router = APIRouter(prefix="/api/v2", tags=["workflows"])

PROCESS_TIMEOUT = 300


class TaskType(str, Enum):
    """Task types for document processing."""

    FULL_FLOW = "full-flow"
    MEDICAL_VERIFICATION = "med-verification"
    DOCUMENT_EXTRACTION = "document-extraction"
    DIAGNOSIS_VERIFICATION = "verify-diagnosis"


TASK_MAPPING = {
    "verify-diagnosis": TaskType.DIAGNOSIS_VERIFICATION,
    "full-flow": TaskType.FULL_FLOW,
    "document-extraction": TaskType.DOCUMENT_EXTRACTION,
    "med-verification": TaskType.MEDICAL_VERIFICATION,
}


class WorkflowInputs(BaseModel):
    """Inputs for workflow endpoint."""

    ocr_res: str = Field(default="{}", description="JSON string containing OCR extracted data")
    task: str = Field(..., description="Task to perform")


class WorkflowRequest(BaseModel):
    """Request model for workflow endpoint."""

    inputs: WorkflowInputs


class DocumentRequest(BaseModel):
    """Request model for direct process endpoint."""

    file_path: str = Field(..., description="Path to PDF document")
    task: TaskType = Field(..., description="Task to perform")
    benefit: str = Field(default="health insurance")
    treatment: str = Field(default="")


# Cache prompt files at module level to avoid repeated file I/O
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_TEMPLATES = {
    TaskType.FULL_FLOW: (_PROMPTS_DIR / "full_flow.md").read_text(encoding="utf-8"),
    TaskType.MEDICAL_VERIFICATION: (_PROMPTS_DIR / "medical_verification.md").read_text(encoding="utf-8"),
    TaskType.DIAGNOSIS_VERIFICATION: (_PROMPTS_DIR / "diagnosis_verification.md").read_text(encoding="utf-8"),
}


def _extract_result_text(result: dict) -> str:
    """Extract textual content from agent response message list."""
    messages = result.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    if hasattr(last_message, "content"):
        content = last_message.content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "".join(parts).strip()
        if isinstance(content, str):
            return content.strip()

    return str(last_message).strip()


def _try_parse_json(text: str):
    """Best-effort JSON parsing for model outputs."""
    if not text:
        return {"result": ""}

    cleaned = text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[-1].split("```")[0].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"result": text}


def load_prompt(task_type: TaskType, ocr_data: dict, benefit: str = "", treatment: str = "") -> str:
    """Load and format prompt for given task type."""
    template = _PROMPT_TEMPLATES.get(task_type)
    if not template:
        raise ValueError(f"No prompt configured for task type: {task_type}")

    if task_type == TaskType.FULL_FLOW:
        file_path = ocr_data.get("file_path", "N/A")
        benefit = benefit or ocr_data.get("benefit", "health insurance")
        treatment = treatment or ocr_data.get("treatment", "")
        base_prompt = template.format(file_path=file_path, benefit=benefit, treatment=treatment)
    else:
        base_prompt = template

    ocr_context = json.dumps(ocr_data, indent=2, ensure_ascii=False)
    return (
        "# CONTEXT - OCR Data\n"
        "The following data has been pre-extracted from documents:\n\n"
        f"```\n{ocr_context}\n```\n\n"
        "---\n\n"
        f"{base_prompt}"
    )


@router.post("/workflows/run")
async def run_workflow(request: WorkflowRequest):
    """Run a workflow with OCR data and task type."""
    try:
        ocr_data = json.loads(request.inputs.ocr_res) if request.inputs.ocr_res else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in ocr_res: {exc}")

    task_type = TASK_MAPPING.get(request.inputs.task)
    if not task_type:
        raise HTTPException(status_code=400, detail=f"Unknown task: {request.inputs.task}")

    try:
        prompt = load_prompt(task_type, ocr_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        async with asyncio.timeout(PROCESS_TIMEOUT):
            result = await asyncio.to_thread(run_agent, prompt, "default")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"Processing timed out after {PROCESS_TIMEOUT}s")

    return _try_parse_json(_extract_result_text(result))


@router.post("/process")
async def process_document(request: DocumentRequest):
    """Process a document with direct task/benefit/treatment inputs."""
    session_id = str(uuid.uuid4())

    # Use cached prompt templates and shared load_prompt function
    prompt = load_prompt(
        request.task,
        ocr_data={"file_path": request.file_path, "benefit": request.benefit, "treatment": request.treatment},
        benefit=request.benefit,
        treatment=request.treatment,
    )

    try:
        async with asyncio.timeout(PROCESS_TIMEOUT):
            result = await asyncio.to_thread(run_agent, prompt, session_id)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"Processing timed out after {PROCESS_TIMEOUT}s")

    return {"session_id": session_id, "result": _extract_result_text(result)}


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "version": "src2-integrated"}
