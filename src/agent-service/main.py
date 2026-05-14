"""Main FastAPI application for agent service."""

from contextlib import asynccontextmanager

import structlog
from api.routes import router as workflows_router
from config import get_cors_origins, settings, validate_startup_config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mongodb_client import close_mongodb_client

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    validate_startup_config()
    logger.info("Starting Agent Service", app_name=app.title, version=settings.APP_VERSION)
    yield
    # Cleanup MongoDB connection on shutdown
    close_mongodb_client()
    logger.info("Shutting down Agent Service")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agent Service - Multi-agent LangGraph workflow",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows_router)


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "endpoints": {
            "health": "/health",
            "workflow_run": "/api/v1/workflows/run (POST)",
            "workflow_resume": "/api/v1/workflows/resume/{run_id} (POST)",
            "workflow_status": "/api/v1/workflows/status/{run_id} (GET)",
        },
    }


@app.get("/health")
async def health() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
