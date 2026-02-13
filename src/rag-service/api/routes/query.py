"""API routes for RAG query operations."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import structlog

from core.search.hybrid_search import HybridSearch

router = APIRouter()
logger = structlog.get_logger()
searcher = HybridSearch()


class RAGQueryRequest(BaseModel):
    """Request for RAG query."""
    query: str = Field(..., description="Query text", min_length=1)
    policy_number: Optional[str] = None
    filters: Optional[dict] = None
    top_k: int = Field(5, ge=1, le=10)


class ContextItem(BaseModel):
    """Single context item."""
    content: str
    source: str
    score: float
    metadata: dict


class RAGQueryResponse(BaseModel):
    """RAG query response."""
    query: str
    context: str
    sources: List[ContextItem]
    total_sources: int


def _extract_doc_types(filters: Optional[dict]) -> Optional[List[str]]:
    """Extract document types from filters."""
    if filters is None:
        return None
    return filters.get("document_type")


def _format_context_item(index: int, content: str) -> str:
    """Format a single context item."""
    return f"[{index}] {content[:800]}..."


def _create_context_item(result: dict) -> ContextItem:
    """Create a ContextItem from search result."""
    return ContextItem(
        content=result["content"][:500],
        source=result.get("metadata", {}).get("source", "unknown"),
        score=result.get("rrf_score", 0),
        metadata=result.get("metadata", {})
    )


@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest) -> RAGQueryResponse:
    """Perform RAG query with context injection.

    Retrieves relevant documents and formats them as context
    for LLM consumption.

    Args:
        request: Query parameters

    Returns:
        Formatted context and sources
    """
    logger.info("RAG query", query=request.query)

    doc_types = _extract_doc_types(request.filters)

    results = await searcher.search(
        query=request.query,
        top_k=request.top_k,
        doc_types=doc_types
    )

    context_parts = [
        _format_context_item(i, result["content"])
        for i, result in enumerate(results, 1)
    ]

    sources = [_create_context_item(result) for result in results]

    logger.info(
        "RAG query completed",
        query=request.query,
        sources=len(sources)
    )

    return RAGQueryResponse(
        query=request.query,
        context="\n\n".join(context_parts),
        sources=sources,
        total_sources=len(sources)
    )


@router.post("/rag/query/simple")
async def rag_query_simple(query: str, top_k: int = 3) -> dict:
    """Simplified RAG query endpoint.

    Args:
        query: Query string
        top_k: Number of results

    Returns:
        Simple context string
    """
    results = await searcher.search(query=query, top_k=top_k)

    context = "\n\n".join([
        f"- {result['content'][:500]}"
        for result in results
    ])

    return {
        "query": query,
        "context": context,
        "sources_found": len(results)
    }
