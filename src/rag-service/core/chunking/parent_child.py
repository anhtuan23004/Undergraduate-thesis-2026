"""Parent-child chunking strategy."""
from typing import List, Dict, Any, Tuple
import re

from app.config import settings


class ParentChildChunker:
    """Chunker implementing parent-child strategy."""

    def __init__(self):
        """Initialize chunker."""
        self.parent_size = settings.PARENT_CHUNK_SIZE
        self.child_size = settings.CHILD_CHUNK_SIZE
        self.overlap = settings.CHUNK_OVERLAP

    def chunk_document(
        self,
        document: str,
        metadata: Dict[str, Any],
        doc_type: str
    ) -> List[Dict[str, Any]]:
        """Chunk document using parent-child strategy.

        Args:
            document: Full document text
            metadata: Document metadata
            doc_type: Document type

        Returns:
            List of chunks with parent-child relationships
        """
        # Split into parent chunks
        parent_chunks = self._split_parent(document)

        all_chunks = []

        for parent_idx, parent in enumerate(parent_chunks):
            parent_id = f"{metadata.get('doc_id', 'doc')}_p{parent_idx}"

            # Create parent chunk
            parent_chunk = {
                'id': parent_id,
                'content': parent,
                'chunk_type': 'parent',
                'parent_id': None,
                'metadata': {
                    **metadata,
                    'parent_index': parent_idx,
                    'total_parents': len(parent_chunks)
                },
                'doc_type': doc_type
            }
            all_chunks.append(parent_chunk)

            # Split parent into child chunks
            child_chunks = self._split_child(parent)

            for child_idx, child in enumerate(child_chunks):
                child_chunk = {
                    'id': f"{parent_id}_c{child_idx}",
                    'content': child,
                    'chunk_type': 'child',
                    'parent_id': parent_id,
                    'metadata': {
                        **metadata,
                        'parent_index': parent_idx,
                        'child_index': child_idx,
                        'total_children': len(child_chunks)
                    },
                    'doc_type': doc_type
                }
                all_chunks.append(child_chunk)

        return all_chunks

    def _split_parent(self, text: str) -> List[str]:
        """Split text into parent chunks."""
        # Try to split on section boundaries first
        sections = re.split(r'\n#{1,3}\s+', text)

        if len(sections) > 1:
            return [s.strip() for s in sections if len(s.strip()) > 100]

        # Fallback to size-based splitting
        return self._split_by_size(text, self.parent_size, overlap=0)

    def _split_child(self, text: str) -> List[str]:
        """Split parent into child chunks with overlap."""
        return self._split_by_size(text, self.child_size, self.overlap)

    def _split_by_size(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Split text by size with overlap.

        Args:
            text: Input text
            chunk_size: Target chunk size
            overlap: Overlap size

        Returns:
            List of chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending
                next_period = text.find('. ', end - 50, end + 50)
                if next_period != -1:
                    end = next_period + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    def chunk_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Chunk multiple documents.

        Args:
            documents: List of document dicts

        Returns:
            List of all chunks
        """
        all_chunks = []

        for doc in documents:
            chunks = self.chunk_document(
                document=doc['content'],
                metadata=doc.get('metadata', {}),
                doc_type=doc.get('doc_type', 'general')
            )
            all_chunks.extend(chunks)

        return all_chunks
