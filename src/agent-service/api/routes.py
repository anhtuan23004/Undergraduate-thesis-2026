"""Workflow API routes using LangGraph workflow with MongoDB persistence.

This module is kept for backward compatibility.
Routes have been split into:
- workflows.py: Workflow execution routes (run, resume, continue)
- upload.py: Document upload routes
- status.py: Status and health check routes
- schemas.py: Pydantic request/response models
- helpers.py: Shared helper functions
"""

from fastapi import APIRouter

from . import status, upload, workflows
from .schemas import ClaimRequest, ContinueRequest, HumanReviewRequest, UploadResponse

router = APIRouter(prefix="/api/v1", tags=["workflows"])

router.include_router(workflows.router)
router.include_router(upload.router)
router.include_router(status.router)

__all__ = [
    "router",
    "ClaimRequest",
    "ContinueRequest",
    "HumanReviewRequest",
    "UploadResponse",
]
