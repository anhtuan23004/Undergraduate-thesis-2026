"""API routes for document ingestion."""
import hashlib
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import structlog

from core.chunking.parent_child import ParentChildChunker
from core.embeddings.generator import EmbeddingGenerator
from db.milvus_client import MilvusClient

router = APIRouter()
logger = structlog.get_logger()

chunker = ParentChildChunker()
embedder = EmbeddingGenerator()
milvus = MilvusClient()


class DocumentIngestRequest(BaseModel):
    """Request for document ingestion."""
    content: str = Field(..., description="Document content", min_length=10)
    doc_type: str = Field(..., description="Document type")
    metadata: dict = Field(default_factory=dict)


class BatchIngestRequest(BaseModel):
    """Request for batch ingestion."""
    documents: List[DocumentIngestRequest]


class IngestResponse(BaseModel):
    """Ingestion response."""
    doc_id: str
    chunks_created: int
    status: str


def _generate_doc_id(content: str, doc_type: str) -> str:
    """Generate a unique document ID."""
    content_hash = hashlib.md5(
        (content[:100] + doc_type).encode()
    ).hexdigest()
    return content_hash[:12]


def _prepare_metadata(
    base_metadata: dict,
    doc_id: str,
    doc_type: str
) -> dict:
    """Prepare metadata with doc_id and doc_type."""
    return {
        **base_metadata,
        "doc_id": doc_id,
        "doc_type": doc_type
    }


def _extract_child_chunks(chunks: List[dict]) -> List[dict]:
    """Extract only child chunks for embedding."""
    return [chunk for chunk in chunks if chunk["chunk_type"] == "child"]


def _prepare_milvus_data(child_chunks: List[dict]) -> dict:
    """Prepare data for Milvus insertion."""
    return {
        "documents": [chunk["content"] for chunk in child_chunks],
        "metadatas": [chunk["metadata"] for chunk in child_chunks],
        "doc_types": [chunk["doc_type"] for chunk in child_chunks],
        "parent_ids": [chunk.get("parent_id", "") for chunk in child_chunks]
    }


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: DocumentIngestRequest) -> IngestResponse:
    """Ingest a single document.

    Chunks document, generates embeddings, and stores in Milvus.

    Args:
        request: Document to ingest

    Returns:
        Ingestion status
    """
    logger.info(
        "Ingesting document",
        doc_type=request.doc_type,
        content_length=len(request.content)
    )

    doc_id = _generate_doc_id(request.content, request.doc_type)
    metadata = _prepare_metadata(request.metadata, doc_id, request.doc_type)

    chunks = chunker.chunk_document(
        document=request.content,
        metadata=metadata,
        doc_type=request.doc_type
    )

    child_chunks = _extract_child_chunks(chunks)

    if not child_chunks:
        return IngestResponse(
            doc_id=doc_id,
            chunks_created=0,
            status="no_chunks"
        )

    embeddings = await embedder.generate_batch(
        [chunk["content"] for chunk in child_chunks]
    )

    milvus_data = _prepare_milvus_data(child_chunks)

    milvus.connect()
    inserted_ids = milvus.insert(
        documents=milvus_data["documents"],
        embeddings=embeddings,
        metadata=milvus_data["metadatas"],
        doc_types=milvus_data["doc_types"],
        parent_ids=milvus_data["parent_ids"]
    )
    milvus.disconnect()

    logger.info(
        "Document ingested",
        doc_id=doc_id,
        chunks=len(chunks),
        inserted=len(inserted_ids)
    )

    return IngestResponse(
        doc_id=doc_id,
        chunks_created=len(chunks),
        status="success"
    )


@router.post("/ingest/batch")
async def ingest_batch(request: BatchIngestRequest) -> dict:
    """Ingest multiple documents.

    Args:
        request: Batch of documents

    Returns:
        Ingestion results
    """
    results = []

    for document in request.documents:
        try:
            result = await ingest_document(document)
            results.append({
                "doc_id": result.doc_id,
                "status": "success",
                "chunks": result.chunks_created
            })
        except Exception as error:
            results.append({
                "status": "error",
                "error": str(error)
            })

    successful_count = sum(
        1 for result in results if result.get("status") == "success"
    )

    return {
        "total": len(request.documents),
        "successful": successful_count,
        "results": results
    }


@router.get("/ingest/stats")
async def get_ingestion_stats() -> dict:
    """Get ingestion statistics."""
    milvus.connect()
    stats = milvus.get_stats()
    milvus.disconnect()

    return stats
