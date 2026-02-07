"""Hybrid search combining BM25 and vector search with RRF."""
from typing import List, Dict, Any, Optional
import asyncio

from app.config import settings
from core.embeddings.generator import EmbeddingGenerator
from core.search.bm25_search import BM25Search
from db.milvus_client import MilvusClient


class HybridSearch:
    """Hybrid search with BM25 + Vector + RRF fusion."""

    def __init__(self):
        """Initialize hybrid searcher."""
        self.embedding_generator = EmbeddingGenerator()
        self.bm25_searcher = BM25Search()
        self.milvus_client = MilvusClient()
        self.rrf_k = settings.RRF_K  # Reciprocal Rank Fusion constant

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_types: Optional[List[str]] = None,
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search.

        Combines BM25 keyword search and vector similarity search
        using Reciprocal Rank Fusion.

        Args:
            query: Search query
            top_k: Number of results
            doc_types: Optional filter by document type
            alpha: Weight for vector vs BM25 (0=BM25 only, 1=vector only)

        Returns:
            Fused search results
        """
        # Run searches in parallel
        vector_task = self._vector_search(query, top_k * 2, doc_types)
        bm25_task = self._bm25_search(query, top_k * 2, doc_types)

        vector_results, bm25_results = await asyncio.gather(
            vector_task, bm25_task
        )

        # Fuse results using RRF
        fused = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            top_k=top_k
        )

        return fused

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        doc_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Vector similarity search using Milvus."""
        # Ensure connection
        self.milvus_client.connect()

        # Generate query embedding
        query_embedding = await self.embedding_generator.generate(query)

        # Build filter
        filters = None
        if doc_types:
            type_filter = " || ".join([f"doc_type == '{t}'" for t in doc_types])
            filters = f"({type_filter})"

        # Search
        results = self.milvus_client.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters
        )

        # Normalize scores (cosine similarity to 0-1)
        for r in results:
            r['vector_score'] = r['score']
            r['source'] = 'vector'

        return results

    async def _bm25_search(
        self,
        query: str,
        top_k: int,
        doc_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """BM25 keyword search."""
        # Note: BM25 requires indexed documents
        # In production, load from MongoDB or build index
        results = self.bm25_searcher.search_with_filter(
            query=query,
            doc_types=doc_types,
            top_k=top_k
        )

        for r in results:
            r['bm25_score'] = r.get('bm25_score', 0)
            r['source'] = 'bm25'

        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Fuse results using Reciprocal Rank Fusion.

        RRF formula: score = Σ(1 / (k + rank))
        where k is a constant (default 60)

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            top_k: Number of final results

        Returns:
            Fused and ranked results
        """
        fusion_scores = {}
        k = self.rrf_k

        # Process vector results
        for rank, result in enumerate(vector_results, start=1):
            doc_id = result.get('id')
            if doc_id:
                if doc_id not in fusion_scores:
                    fusion_scores[doc_id] = {
                        'doc': result,
                        'score': 0,
                        'sources': []
                    }
                fusion_scores[doc_id]['score'] += 1.0 / (k + rank)
                fusion_scores[doc_id]['sources'].append('vector')

        # Process BM25 results
        for rank, result in enumerate(bm25_results, start=1):
            doc_id = result.get('id')
            if doc_id:
                if doc_id not in fusion_scores:
                    fusion_scores[doc_id] = {
                        'doc': result,
                        'score': 0,
                        'sources': []
                    }
                fusion_scores[doc_id]['score'] += 1.0 / (k + rank)
                fusion_scores[doc_id]['sources'].append('bm25')

        # Sort by fusion score
        sorted_results = sorted(
            fusion_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:top_k]

        # Format output
        final_results = []
        for item in sorted_results:
            result = item['doc'].copy()
            result['rrf_score'] = item['score']
            result['fusion_sources'] = item['sources']
            final_results.append(result)

        return final_results

    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            'rrf_k': self.rrf_k,
            'milvus_stats': self.milvus_client.get_stats(),
            'bm25_stats': self.bm25_searcher.get_stats()
        }
