"""Upload and workflow input path policy helpers."""

from __future__ import annotations

from pathlib import Path

from config import settings
from fastapi import HTTPException

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_UPLOAD_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}
UPLOAD_MIME_TYPES_BY_EXTENSION = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}


def resolve_upload_dir() -> Path:
    """Return the configured uploads directory as an absolute path."""
    return Path(settings.UPLOADS_DIR).expanduser().resolve()


def safe_upload_filename(filename: str | None) -> str:
    """Return a basename-only filename suitable for storing under UPLOADS_DIR."""
    safe_name = Path(filename or "claim_document").name
    if not safe_name or safe_name in {".", ".."}:
        return "claim_document"
    return safe_name


def validate_upload_metadata(filename: str | None, mime_type: str | None) -> None:
    """Validate uploaded claim document extension and MIME type."""
    safe_name = safe_upload_filename(filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file extension. Allowed extensions: "
                f"{', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
            ),
        )

    normalized_mime = (mime_type or "").split(";", 1)[0].strip().lower()
    if normalized_mime not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file MIME type. Allowed MIME types: "
                f"{', '.join(sorted(ALLOWED_UPLOAD_MIME_TYPES))}"
            ),
        )

    allowed_mime_types = UPLOAD_MIME_TYPES_BY_EXTENSION[extension]
    if normalized_mime not in allowed_mime_types:
        raise HTTPException(
            status_code=415,
            detail=(
                "File extension does not match MIME type. "
                f"Extension {extension} requires: {', '.join(sorted(allowed_mime_types))}"
            ),
        )


def resolve_upload_path(file_path: str) -> Path:
    """Resolve workflow input paths and restrict them to UPLOADS_DIR."""
    if not file_path or not str(file_path).strip():
        raise HTTPException(status_code=400, detail="Input file path is required")

    upload_dir = resolve_upload_dir()
    candidate = Path(file_path).expanduser()
    resolved = (
        candidate.resolve() if candidate.is_absolute() else (upload_dir / candidate).resolve()
    )

    try:
        resolved.relative_to(upload_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Input file must be inside UPLOADS_DIR",
        ) from exc

    return resolved
