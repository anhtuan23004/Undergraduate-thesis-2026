"""API routes for search operations."""
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
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


def _format_search_results(results: List[dict]) -> List[SearchResult]:
    """Format raw search results into response model."""
    return [
        SearchResult(
            id=result["id"],
            content=result["content"][:500],
            score=result.get("rrf_score", 0),
            doc_type=result["doc_type"],
            metadata=result.get("metadata", {}),
            sources=result.get("fusion_sources", [])
        )
        for result in results
    ]


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Perform hybrid search (BM25 + Vector + RRF).

    Args:
        request: Search parameters

    Returns:
        Ranked search results
    """
    start_time = time.time()

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

    search_time_ms = int((time.time() - start_time) * 1000)
    formatted_results = _format_search_results(results)

    logger.info(
        "Search completed",
        query=request.query,
        results=len(formatted_results),
        time_ms=search_time_ms
    )

    return SearchResponse(
        query=request.query,
        results=formatted_results,
        total_results=len(formatted_results),
        search_time_ms=search_time_ms
    )


@router.get("/search/stats")
async def get_stats() -> dict:
    """Get search statistics."""
    return searcher.get_stats()
