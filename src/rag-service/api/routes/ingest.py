"""API routes for document ingestion."""
from typing import List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
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


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: DocumentIngestRequest):
    """Ingest a single document.

    Chunks document, generates embeddings, and stores in Milvus.

    Args:
        request: Document to ingest

    Returns:
        Ingestion status
    """
    try:
        logger.info(
            "Ingesting document",
            doc_type=request.doc_type,
            content_length=len(request.content)
        )

        # Generate doc_id
        import hashlib
        doc_id = hashlib.md5(
            (request.content[:100] + request.doc_type).encode()
        ).hexdigest()[:12]

        # Add doc_id to metadata
        metadata = {
            **request.metadata,
            "doc_id": doc_id,
            "doc_type": request.doc_type
        }

        # Chunk document
        chunks = chunker.chunk_document(
            document=request.content,
            metadata=metadata,
            doc_type=request.doc_type
        )

        # Generate embeddings (only for child chunks)
        child_chunks = [c for c in chunks if c['chunk_type'] == 'child']

        if child_chunks:
            embeddings = await embedder.generate_batch(
                [c['content'] for c in child_chunks]
            )

            # Prepare for Milvus
            documents = [c['content'] for c in child_chunks]
            metadatas = [c['metadata'] for c in child_chunks]
            doc_types = [c['doc_type'] for c in child_chunks]
            parent_ids = [c.get('parent_id', '') for c in child_chunks]

            # Insert to Milvus
            milvus.connect()
            ids = milvus.insert(
                documents=documents,
                embeddings=embeddings,
                metadata=metadatas,
                doc_types=doc_types,
                parent_ids=parent_ids
            )
            milvus.disconnect()

            logger.info(
                "Document ingested",
                doc_id=doc_id,
                chunks=len(chunks),
                inserted=len(ids)
            )

            return IngestResponse(
                doc_id=doc_id,
                chunks_created=len(chunks),
                status="success"
            )

        return IngestResponse(
            doc_id=doc_id,
            chunks_created=0,
            status="no_chunks"
        )

    except Exception as e:
        logger.error("Ingestion error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/batch")
async def ingest_batch(request: BatchIngestRequest):
    """Ingest multiple documents.

    Args:
        request: Batch of documents

    Returns:
        Ingestion results
    """
    results = []

    for doc in request.documents:
        try:
            result = await ingest_document(doc)
            results.append({
                "doc_id": result.doc_id,
                "status": "success",
                "chunks": result.chunks_created
            })
        except Exception as e:
            results.append({
                "status": "error",
                "error": str(e)
            })

    return {
        "total": len(request.documents),
        "successful": sum(1 for r in results if r.get("status") == "success"),
        "results": results
    }


@router.get("/ingest/stats")
async def get_ingestion_stats():
    """Get ingestion statistics."""
    milvus.connect()
    stats = milvus.get_stats()
    milvus.disconnect()

    return stats