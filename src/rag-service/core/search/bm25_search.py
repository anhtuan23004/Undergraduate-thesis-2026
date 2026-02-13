"""BM25 keyword search implementation."""
import re
from typing import Any, Dict, List, Optional

import jieba
from rank_bm25 import BM25Okapi

from app.config import settings


class BM25Search:
    """BM25 keyword search for document retrieval."""

    def __init__(self) -> None:
        """Initialize BM25 searcher."""
        self._documents: List[Dict[str, Any]] = []
        self._tokenized_docs: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None
        self._k1 = settings.BM25_K1
        self._b = settings.BM25_B

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25.

        Supports Vietnamese and English text.

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        cleaned_text = re.sub(r"[^\w\s]", " ", text.lower())

        try:
            tokens = list(jieba.cut(cleaned_text))
        except Exception:
            tokens = cleaned_text.split()

        return [token.strip() for token in tokens if token.strip()]

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to BM25 index.

        Args:
            documents: List of document dicts with 'content' field
        """
        self._documents = documents
        self._tokenized_docs = [
            self._tokenize(doc["content"])
            for doc in documents
        ]

        if self._tokenized_docs:
            self._bm25 = BM25Okapi(
                self._tokenized_docs,
                k1=self._k1,
                b=self._b
            )

    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search documents using BM25.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of results with BM25 scores
        """
        if not self._bm25:
            return []

        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        top_indices = sorted(
            range(len(scores)),
            key=lambda idx: scores[idx],
            reverse=True
        )[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue

            result = self._documents[idx].copy()
            result["bm25_score"] = float(scores[idx])
            result["rank"] = len(results) + 1
            results.append(result)

        return results

    def search_with_filter(
        self,
        query: str,
        doc_types: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search with document type filter.

        Args:
            query: Search query
            doc_types: Optional list of doc types to filter
            top_k: Number of results

        Returns:
            Filtered results
        """
        results = self.search(query, top_k=top_k * 2)

        if doc_types:
            results = [
                result for result in results
                if result.get("doc_type") in doc_types
            ]

        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        total_tokens = sum(len(doc) for doc in self._tokenized_docs)
        doc_count = len(self._tokenized_docs)

        return {
            "total_documents": doc_count,
            "avg_doc_length": total_tokens / max(doc_count, 1),
            "k1": self._k1,
            "b": self._b
        }
