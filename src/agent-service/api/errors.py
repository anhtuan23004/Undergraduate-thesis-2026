"""Unified error helpers for workflow API endpoints."""

from fastapi import HTTPException


def workflow_error(
    status_code: int,
    detail: str,
    *,
    error_detail: str | None = None,
    endpoint: str | None = None,
) -> HTTPException:
    """Create an HTTPException with a structured detail payload.

    Args:
        status_code: HTTP status code.
        detail: Human-readable error message.
        error_detail: Optional technical detail.
        endpoint: Optional originating endpoint for debugging.

    Returns:
        HTTPException with structured detail dict.
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "error": detail,
            "error_detail": error_detail,
            "status_code": status_code,
            "endpoint": endpoint,
        },
    )
