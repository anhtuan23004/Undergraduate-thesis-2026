"""BM25 keyword search implementation."""
from typing import List, Dict, Any, Optional
import re
import jieba
from rank_bm25 import BM25Okapi

from app.config import settings


class BM25Search:
    """BM25 keyword search for document retrieval."""

    def __init__(self):
        """Initialize BM25 searcher."""
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_docs: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.k1 = settings.BM25_K1
        self.b = settings.BM25_B

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25.

        Supports Vietnamese and English text.

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        # Lowercase and remove special chars
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)

        # Try jieba for Chinese, fallback to simple split
        try:
            tokens = list(jieba.cut(text))
        except:
            tokens = text.split()

        # Filter empty tokens
        return [t.strip() for t in tokens if t.strip()]

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to BM25 index.

        Args:
            documents: List of document dicts with 'content' field
        """
        self.documents = documents
        self.tokenized_docs = [
            self._tokenize(doc['content'])
            for doc in documents
        ]

        # Build BM25 index
        if self.tokenized_docs:
            self.bm25 = BM25Okapi(
                self.tokenized_docs,
                k1=self.k1,
                b=self.b
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
        if not self.bm25:
            return []

        # Tokenize query
        tokenized_query = self._tokenize(query)

        # Get scores
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:top_k]

        # Format results
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only return positive scores
                result = self.documents[idx].copy()
                result['bm25_score'] = float(scores[idx])
                result['rank'] = len(results) + 1
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
        results = self.search(query, top_k=top_k * 2)  # Get more for filtering

        if doc_types:
            results = [
                r for r in results
                if r.get('doc_type') in doc_types
            ]

        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            'total_documents': len(self.documents),
            'avg_doc_length': sum(len(d) for d in self.tokenized_docs) / max(len(self.tokenized_docs), 1),
            'k1': self.k1,
            'b': self.b
        }
