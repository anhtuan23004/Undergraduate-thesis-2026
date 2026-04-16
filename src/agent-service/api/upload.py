"""Upload API routes for workflow documents."""

import uuid
from pathlib import Path

from config import settings
from fastapi import APIRouter, File, HTTPException, UploadFile

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
        upload_dir = Path(settings.UPLOADS_DIR).expanduser().resolve()
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(file.filename or "claim_document").name
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        output_path = upload_dir / unique_name

        content = await file.read()
        file_hash = compute_file_hash(content)

        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB}MB",
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
            status_code=500, detail=f"Failed to save uploaded file: {str(e)}"
        ) from e
