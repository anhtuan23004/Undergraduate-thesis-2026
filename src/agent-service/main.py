"""Main FastAPI application for agent service."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from interfaces.api.routes import router as multi_agent_router
from core.storage.redis_storage import get_storage

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
# For production, set ALLOWED_ORIGINS env var to your frontend domain(s):
# Example: ALLOWED_ORIGINS=https://your-domain.com,https://app.your-domain.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else ["*"],
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
                "process": "/api/v1/multi-agent/process (POST)",
                "status": "/api/v1/multi-agent/status/{claim_id} (GET)",
                "pending_reviews": "/api/v1/multi-agent/pending-reviews (GET)",
                "submit_review": "/api/v1/multi-agent/submit-review/{claim_id} (POST)"
            }
        }
    }


@app.get("/health")
async def health() -> dict:
    """Health check with Redis connectivity status."""
    redis_status = "unknown"
    try:
        storage = get_storage()
        if storage and await storage.ping():
            redis_status = "connected"
        else:
            redis_status = "disconnected"
    except Exception:
        redis_status = "error"
    
    is_healthy = redis_status == "connected"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "redis": redis_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
