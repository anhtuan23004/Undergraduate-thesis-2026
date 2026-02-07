"""Milvus client for vector database operations."""
from typing import List, Dict, Any, Optional
import numpy as np
from pymilvus import (
    connections,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    utility
)

from app.config import settings


class MilvusClient:
    """Client for Milvus vector database."""

    def __init__(self):
        """Initialize Milvus connection."""
        self.host = settings.MILVUS_HOST
        self.port = settings.MILVUS_PORT
        self.collection_name = settings.MILVUS_COLLECTION
        self.dim = settings.MILVUS_DIM
        self._collection = None

    def connect(self):
        """Connect to Milvus server."""
        connections.connect(
            alias="default",
            host=self.host,
            port=self.port
        )

    def disconnect(self):
        """Disconnect from Milvus."""
        connections.disconnect("default")

    def drop_collection(self) -> None:
        """Drop the existing collection."""
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            self._collection = None

    def create_collection(self) -> Collection:
        """Create knowledge base collection with schema."""
        # Define fields
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                max_length=64,
                is_primary=True,
                auto_id=True
            ),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=65535
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.dim
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.JSON
            ),
            FieldSchema(
                name="doc_type",
                dtype=DataType.VARCHAR,
                max_length=64
            ),
            FieldSchema(
                name="parent_id",
                dtype=DataType.VARCHAR,
                max_length=64
            )
        ]

        # Create schema
        schema = CollectionSchema(
            fields=fields,
            description="Knowledge base for insurance claims",
            enable_dynamic_field=True
        )

        # Create collection
        collection = Collection(
            name=self.collection_name,
            schema=schema,
            using='default',
            shards_num=2
        )

        # Create HNSW index
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {
                "M": 16,
                "efConstruction": 200
            }
        }

        collection.create_index(
            field_name="embedding",
            index_params=index_params
        )

        # Create index on doc_type for filtering
        collection.create_index(
            field_name="doc_type",
            index_params={"index_type": "Trie"}
        )

        return collection

    def get_collection(self) -> Collection:
        """Get or create collection."""
        if self._collection is None:
            if utility.has_collection(self.collection_name):
                # Check if existing collection has correct dimension
                collection = Collection(self.collection_name)
                for field in collection.schema.fields:
                    if field.name == "embedding":
                        existing_dim = field.params.get("dim")
                        if existing_dim != self.dim:
                            print(f"Collection has wrong dimension {existing_dim}, dropping and recreating with {self.dim}")
                            utility.drop_collection(self.collection_name)
                            self._collection = self.create_collection()
                        else:
                            self._collection = collection
                        break
                else:
                    self._collection = collection
            else:
                self._collection = self.create_collection()
        return self._collection

    def insert(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]],
        doc_types: List[str],
        parent_ids: Optional[List[str]] = None
    ) -> List[str]:
        """Insert documents with embeddings.

        Args:
            documents: List of document chunks
            embeddings: List of embedding vectors
            metadata: List of metadata dicts
            doc_types: List of document types
            parent_ids: Optional parent chunk IDs

        Returns:
            List of inserted IDs
        """
        collection = self.get_collection()

        if parent_ids is None:
            parent_ids = [""] * len(documents)

        entities = [
            documents,
            embeddings,
            metadata,
            doc_types,
            parent_ids
        ]

        result = collection.insert(entities)
        collection.flush()

        return result.primary_keys

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[str] = None,
        ef: int = 64
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_embedding: Query vector
            top_k: Number of results
            filters: Optional filter expression
            ef: Search scope parameter

        Returns:
            List of search results with scores
        """
        collection = self.get_collection()
        collection.load()

        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": ef}
        }

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filters,
            output_fields=["content", "metadata", "doc_type", "parent_id"]
        )

        # Format results
        formatted = []
        for hits in results:
            for hit in hits:
                formatted.append({
                    "id": hit.id,
                    "score": hit.score,
                    "content": hit.entity.get("content"),
                    "metadata": hit.entity.get("metadata"),
                    "doc_type": hit.entity.get("doc_type"),
                    "parent_id": hit.entity.get("parent_id")
                })

        return formatted

    def delete(self, expr: str) -> None:
        """Delete entities by expression.

        Args:
            expr: Delete expression (e.g., "doc_type == 'old_policy'")
        """
        collection = self.get_collection()
        collection.delete(expr)

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        collection = self.get_collection()
        collection.flush()

        return {
            "total_documents": collection.num_entities,
            "collection_name": self.collection_name,
            "dimension": self.dim
        }
