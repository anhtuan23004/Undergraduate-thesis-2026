"""Main FastAPI application for agent service."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import agent
from app.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        "Starting Agent Service",
        version=settings.APP_VERSION,
        model=settings.OPENAI_MODEL
    )
    yield
    logger.info("Shutting down Agent Service")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ReAct Agent for Insurance Claims Processing",
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
app.include_router(agent.router, prefix="/api/v1", tags=["agent"])


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "architecture": "ReAct Agent with LangGraph",
        "endpoints": {
            "health": "/api/v1/agent/health",
            "decide": "/api/v1/agent/decide (POST)",
            "graph": "/api/v1/agent/graph"
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
