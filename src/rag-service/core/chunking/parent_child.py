"""Parent-child chunking strategy."""
import re
from typing import Any, Dict, List

from app.config import settings


class ParentChildChunker:
    """Chunker implementing parent-child strategy."""

    def __init__(self) -> None:
        """Initialize chunker."""
        self._parent_size = settings.PARENT_CHUNK_SIZE
        self._child_size = settings.CHILD_CHUNK_SIZE
        self._overlap = settings.CHUNK_OVERLAP

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
        parent_chunks = self._split_into_parents(document)
        doc_id = metadata.get("doc_id", "doc")

        all_chunks: List[Dict[str, Any]] = []

        for parent_index, parent_content in enumerate(parent_chunks):
            parent_id = f"{doc_id}_p{parent_index}"
            parent_chunk = self._create_parent_chunk(
                parent_id=parent_id,
                content=parent_content,
                metadata=metadata,
                doc_type=doc_type,
                parent_index=parent_index,
                total_parents=len(parent_chunks)
            )
            all_chunks.append(parent_chunk)

            child_chunks = self._split_parent_into_children(parent_content)
            for child_index, child_content in enumerate(child_chunks):
                child_chunk = self._create_child_chunk(
                    parent_id=parent_id,
                    content=child_content,
                    metadata=metadata,
                    doc_type=doc_type,
                    parent_index=parent_index,
                    child_index=child_index,
                    total_children=len(child_chunks)
                )
                all_chunks.append(child_chunk)

        return all_chunks

    def _create_parent_chunk(
        self,
        parent_id: str,
        content: str,
        metadata: Dict[str, Any],
        doc_type: str,
        parent_index: int,
        total_parents: int
    ) -> Dict[str, Any]:
        """Create a parent chunk."""
        return {
            "id": parent_id,
            "content": content,
            "chunk_type": "parent",
            "parent_id": None,
            "metadata": {
                **metadata,
                "parent_index": parent_index,
                "total_parents": total_parents
            },
            "doc_type": doc_type
        }

    def _create_child_chunk(
        self,
        parent_id: str,
        content: str,
        metadata: Dict[str, Any],
        doc_type: str,
        parent_index: int,
        child_index: int,
        total_children: int
    ) -> Dict[str, Any]:
        """Create a child chunk."""
        return {
            "id": f"{parent_id}_c{child_index}",
            "content": content,
            "chunk_type": "child",
            "parent_id": parent_id,
            "metadata": {
                **metadata,
                "parent_index": parent_index,
                "child_index": child_index,
                "total_children": total_children
            },
            "doc_type": doc_type
        }

    def _split_into_parents(self, text: str) -> List[str]:
        """Split text into parent chunks."""
        sections = re.split(r"\n#{1,3}\s+", text)

        if len(sections) > 1:
            return [s.strip() for s in sections if len(s.strip()) > 100]

        return self._split_by_size(text, self._parent_size, overlap=0)

    def _split_parent_into_children(self, text: str) -> List[str]:
        """Split parent into child chunks with overlap."""
        return self._split_by_size(text, self._child_size, self._overlap)

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
        if not text:
            return []

        chunks: List[str] = []
        start = 0

        while start < len(text):
            end = self._find_chunk_end(text, start, chunk_size)
            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            start = end - overlap
            if start >= len(text):
                break

        return chunks

    def _find_chunk_end(self, text: str, start: int, chunk_size: int) -> int:
        """Find the best end position for a chunk."""
        end = min(start + chunk_size, len(text))

        if end >= len(text):
            return end

        search_start = max(end - 50, start)
        search_end = min(end + 50, len(text))
        next_period = text.find(". ", search_start, search_end)

        if next_period != -1:
            return next_period + 1

        return end

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
        all_chunks: List[Dict[str, Any]] = []

        for document in documents:
            chunks = self.chunk_document(
                document=document["content"],
                metadata=document.get("metadata", {}),
                doc_type=document.get("doc_type", "general")
            )
            all_chunks.extend(chunks)

        return all_chunks
