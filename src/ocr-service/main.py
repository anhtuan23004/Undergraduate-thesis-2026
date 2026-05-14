"""Main FastAPI application for the OCR service."""

from api.routes import health_router, ocr_router_v1, ocr_router_v2, ocr_router_v2_form
from core.config import settings
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from utils.logging import get_logger, setup_logging

# Configure logging on module load
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle validation errors with simplified error messages.

    Args:
        request: The incoming request.
        exc: The validation exception.

    Returns:
        JSONResponse with simplified error messages.
    """
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        message = error["msg"]
        errors.append(f"{field}: {message}")

    detail = errors[0] if len(errors) == 1 else errors if errors else "Validation error"
    logger.warning("Request validation failed", extra={"path": request.url.path})

    return JSONResponse(
        status_code=422,
        content={"detail": detail},
    )


# Include routers
app.include_router(health_router)
app.include_router(ocr_router_v1)
app.include_router(ocr_router_v2)
app.include_router(ocr_router_v2_form)
