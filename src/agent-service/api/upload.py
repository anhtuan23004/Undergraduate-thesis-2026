"""Upload API routes for workflow documents."""

import mimetypes
import uuid

from config import settings
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from services.file_policy import (
    resolve_upload_dir,
    resolve_upload_path,
    safe_upload_filename,
    validate_upload_metadata,
)
from services.graph_service import get_graph

from .helpers import compute_file_hash
from .schemas import UploadResponse

router = APIRouter(prefix="", tags=["uploads"])


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
        validate_upload_metadata(file.filename, file.content_type)

        upload_dir = resolve_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = safe_upload_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        output_path = upload_dir / unique_name

        content = await file.read()
        file_hash = compute_file_hash(content)

        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Tệp quá lớn. Kích thước tối đa là {settings.MAX_UPLOAD_SIZE_MB}MB",
            )

        output_path.write_bytes(content)

        return UploadResponse(
            filename=safe_name,
            file_path=str(output_path),
            size_bytes=len(content),
            file_hash=file_hash,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Không thể lưu tệp đã tải lên: {str(e)}"
        ) from e


@router.get("/workflows/document/{run_id}")
async def view_workflow_document(run_id: str) -> FileResponse:
    """Return the uploaded workflow document for browser preview."""
    graph = await get_graph()
    config = {"configurable": {"thread_id": run_id}}
    state = await graph.aget_state(config)

    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lượt chạy {run_id}")

    input_file = state.values.get("input_file")
    file_path = resolve_upload_path(input_file)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu đã tải lên")

    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
        content_disposition_type="inline",
    )
