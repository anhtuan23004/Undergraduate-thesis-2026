"""Main FastAPI application for agent service."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from api.routes import router as multi_agent_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        "Starting Agent Service",
        version=settings.APP_VERSION,
    )
    yield
    logger.info("Shutting down Agent Service")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-Agent Insurance Claims Processing",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(multi_agent_router, prefix="/api/v1", tags=["multi-agent"])


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "architecture": "Multi-Agent LangGraph Workflow",
        "endpoints": {
            "health": "/health",
            "multi-agent": {
                "health": "/api/v1/multi-agent/health",
                "process": "/api/v1/multi-agent/process (POST)"
            }
        }
    }


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
