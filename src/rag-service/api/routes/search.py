"""API routes for search operations."""
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import structlog

from core.search.hybrid_search import HybridSearch

router = APIRouter()
logger = structlog.get_logger()
searcher = HybridSearch()


class SearchRequest(BaseModel):
    """Request for hybrid search."""
    query: str = Field(..., description="Search query", min_length=1)
    top_k: int = Field(5, ge=1, le=20, description="Number of results")
    doc_types: Optional[List[str]] = Field(
        None,
        description="Filter by document types"
    )


class SearchResult(BaseModel):
    """Single search result."""
    id: str
    content: str
    score: float
    doc_type: str
    metadata: dict
    sources: List[str]


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: int


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform hybrid search (BM25 + Vector + RRF).

    Args:
        request: Search parameters

    Returns:
        Ranked search results
    """
    import time
    start_time = time.time()

    try:
        logger.info(
            "Performing search",
            query=request.query,
            doc_types=request.doc_types
        )

        results = await searcher.search(
            query=request.query,
            top_k=request.top_k,
            doc_types=request.doc_types
        )

        search_time = int((time.time() - start_time) * 1000)

        # Format results
        formatted_results = [
            SearchResult(
                id=r['id'],
                content=r['content'][:500],  # Truncate for response
                score=r.get('rrf_score', 0),
                doc_type=r['doc_type'],
                metadata=r.get('metadata', {}),
                sources=r.get('fusion_sources', [])
            )
            for r in results
        ]

        logger.info(
            "Search completed",
            query=request.query,
            results=len(formatted_results),
            time_ms=search_time
        )

        return SearchResponse(
            query=request.query,
            results=formatted_results,
            total_results=len(formatted_results),
            search_time_ms=search_time
        )

    except Exception as e:
        logger.error("Search error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/stats")
async def get_stats():
    """Get search statistics."""
    return searcher.get_stats()