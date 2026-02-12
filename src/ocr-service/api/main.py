"""Main FastAPI application for the OCR service."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routes import health_router, ocr_router
from app.config import settings
from utils.logging import setup_logging

# Configure logging on module load
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
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

    return JSONResponse(
        status_code=422,
        content={"detail": detail},
    )


# Include routers
app.include_router(health_router)
app.include_router(ocr_router)
