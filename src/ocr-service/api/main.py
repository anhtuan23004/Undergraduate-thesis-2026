from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from utils.logging import setup_logging
from api.routes import health_router, ocr_router
from app.config import settings

# Configure Logging
setup_logging()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Custom validation error handler that returns only error messages.
    
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
    
    return JSONResponse(
        status_code=422,
        content={"detail": errors if len(errors) > 1 else errors[0] if errors else "Validation error"}
    )


# Include Routers
app.include_router(health_router)
app.include_router(ocr_router)
