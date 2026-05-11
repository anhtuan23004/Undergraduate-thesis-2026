"""Upload API routes for workflow documents."""

import uuid

from config import settings
from fastapi import APIRouter, File, HTTPException, UploadFile
from services.file_policy import resolve_upload_dir, safe_upload_filename, validate_upload_metadata

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
