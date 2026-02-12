"""Main FastAPI application for RAG service."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import ingest, query, search
from app.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(
        "Starting RAG Service",
        version=settings.APP_VERSION
    )
    yield
    logger.info("Shutting down RAG Service")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RAG Service with Hybrid Search (BM25 + Vector)",
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
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(query.router, prefix="/api/v1", tags=["rag"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "features": [
            "Hybrid Search (BM25 + Vector)",
            "Reciprocal Rank Fusion",
            "Parent-Child Chunking",
            "Gemini Embeddings",
            "Milvus Vector DB"
        ],
        "endpoints": {
            "search": "/api/v1/search",
            "rag_query": "/api/v1/rag/query",
            "ingest": "/api/v1/ingest"
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
