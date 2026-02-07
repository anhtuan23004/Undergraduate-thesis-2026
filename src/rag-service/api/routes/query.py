"""API routes for RAG query operations."""
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import structlog

from core.search.hybrid_search import HybridSearch
from core.embeddings.generator import EmbeddingGenerator

router = APIRouter()
logger = structlog.get_logger()
searcher = HybridSearch()
embedder = EmbeddingGenerator()


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


@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """Perform RAG query with context injection.

    Retrieves relevant documents and formats them as context
    for LLM consumption.

    Args:
        request: Query parameters

    Returns:
        Formatted context and sources
    """
    try:
        logger.info("RAG query", query=request.query)

        # Determine doc types to search
        doc_types = None
        if request.filters:
            doc_types = request.filters.get("document_type")

        # Search for relevant documents
        results = await searcher.search(
            query=request.query,
            top_k=request.top_k,
            doc_types=doc_types
        )

        # Format context
        context_parts = []
        sources = []

        for i, result in enumerate(results, 1):
            # Add to context
            context_parts.append(
                f"[{i}] {result['content'][:800]}..."
            )

            # Track source
            sources.append(ContextItem(
                content=result['content'][:500],
                source=result.get('metadata', {}).get('source', 'unknown'),
                score=result.get('rrf_score', 0),
                metadata=result.get('metadata', {})
            ))

        # Join context
        context = "\n\n".join(context_parts)

        logger.info(
            "RAG query completed",
            query=request.query,
            sources=len(sources)
        )

        return RAGQueryResponse(
            query=request.query,
            context=context,
            sources=sources,
            total_sources=len(sources)
        )

    except Exception as e:
        logger.error("RAG query error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/query/simple")
async def rag_query_simple(query: str, top_k: int = 3):
    """Simplified RAG query endpoint.

    Args:
        query: Query string
        top_k: Number of results

    Returns:
        Simple context string
    """
    results = await searcher.search(query=query, top_k=top_k)

    context = "\n\n".join([
        f"- {r['content'][:500]}"
        for r in results
    ])

    return {
        "query": query,
        "context": context,
        "sources_found": len(results)
    }