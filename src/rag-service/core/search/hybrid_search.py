"""Hybrid search combining BM25 and vector search with RRF."""
import asyncio
from typing import Any, Dict, List, Optional

from app.config import settings
from core.embeddings.generator import EmbeddingGenerator
from core.search.bm25_search import BM25Search
from db.milvus_client import MilvusClient


class HybridSearch:
    """Hybrid search with BM25 + Vector + RRF fusion."""

    def __init__(self) -> None:
        """Initialize hybrid searcher."""
        self._embedding_generator = EmbeddingGenerator()
        self._bm25_searcher = BM25Search()
        self._milvus_client = MilvusClient()
        self._rrf_k = settings.RRF_K

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search.

        Combines BM25 keyword search and vector similarity search
        using Reciprocal Rank Fusion.

        Args:
            query: Search query
            top_k: Number of results
            doc_types: Optional filter by document type

        Returns:
            Fused search results
        """
        vector_task = self._vector_search(query, top_k * 2, doc_types)
        bm25_task = self._bm25_search(query, top_k * 2, doc_types)

        vector_results, bm25_results = await asyncio.gather(
            vector_task, bm25_task
        )

        return self._fuse_results(vector_results, bm25_results, top_k)

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        doc_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Vector similarity search using Milvus."""
        self._milvus_client.connect()

        query_embedding = await self._embedding_generator.generate_query_embedding(query)
        filter_expression = self._build_filter_expression(doc_types)

        results = self._milvus_client.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expression
        )

        for result in results:
            result["vector_score"] = result["score"]
            result["source"] = "vector"

        return results

    def _build_filter_expression(
        self,
        doc_types: Optional[List[str]]
    ) -> Optional[str]:
        """Build Milvus filter expression for document types."""
        if not doc_types:
            return None

        type_conditions = [f"doc_type == '{doc_type}'" for doc_type in doc_types]
        return f"({' || '.join(type_conditions)})"

    async def _bm25_search(
        self,
        query: str,
        top_k: int,
        doc_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """BM25 keyword search."""
        results = self._bm25_searcher.search_with_filter(
            query=query,
            doc_types=doc_types,
            top_k=top_k
        )

        for result in results:
            result["bm25_score"] = result.get("bm25_score", 0)
            result["source"] = "bm25"

        return results

    def _fuse_results(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Fuse results using Reciprocal Rank Fusion.

        RRF formula: score = sum(1 / (k + rank))
        where k is a constant (default 60)

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            top_k: Number of final results

        Returns:
            Fused and ranked results
        """
        fusion_scores: Dict[str, Dict[str, Any]] = {}

        self._add_results_to_fusion(fusion_scores, vector_results, "vector")
        self._add_results_to_fusion(fusion_scores, bm25_results, "bm25")

        sorted_results = sorted(
            fusion_scores.values(),
            key=lambda item: item["score"],
            reverse=True
        )[:top_k]

        return self._format_fused_results(sorted_results)

    def _add_results_to_fusion(
        self,
        fusion_scores: Dict[str, Dict[str, Any]],
        results: List[Dict[str, Any]],
        source_name: str
    ) -> None:
        """Add search results to fusion scores."""
        for rank, result in enumerate(results, start=1):
            doc_id = result.get("id")
            if not doc_id:
                continue

            if doc_id not in fusion_scores:
                fusion_scores[doc_id] = {
                    "doc": result,
                    "score": 0.0,
                    "sources": []
                }

            fusion_scores[doc_id]["score"] += 1.0 / (self._rrf_k + rank)
            fusion_scores[doc_id]["sources"].append(source_name)

    def _format_fused_results(
        self,
        sorted_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format fused results for output."""
        formatted = []
        for item in sorted_results:
            result = item["doc"].copy()
            result["rrf_score"] = item["score"]
            result["fusion_sources"] = item["sources"]
            formatted.append(result)
        return formatted

    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            "rrf_k": self._rrf_k,
            "milvus_stats": self._milvus_client.get_stats(),
            "bm25_stats": self._bm25_searcher.get_stats()
        }

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index documents into BM25 for keyword retrieval.

        Args:
            documents: Documents with at least 'content' and optional 'id'
        """
        self._bm25_searcher.append_documents(documents)
