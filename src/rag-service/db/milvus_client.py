"""Milvus client for vector database operations."""
from typing import Any, Dict, List, Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility
)

from app.config import settings


class MilvusClient:
    """Client for Milvus vector database."""

    def __init__(self) -> None:
        """Initialize Milvus connection settings."""
        self._host = settings.MILVUS_HOST
        self._port = settings.MILVUS_PORT
        self._collection_name = settings.MILVUS_COLLECTION
        self._dimension = settings.MILVUS_DIM
        self._collection: Optional[Collection] = None

    def connect(self) -> None:
        """Connect to Milvus server."""
        connections.connect(
            alias="default",
            host=self._host,
            port=self._port
        )

    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        connections.disconnect("default")

    def drop_collection(self) -> None:
        """Drop the existing collection."""
        if utility.has_collection(self._collection_name):
            utility.drop_collection(self._collection_name)
            self._collection = None

    def _create_schema(self) -> CollectionSchema:
        """Create collection schema."""
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
                dim=self._dimension
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

        return CollectionSchema(
            fields=fields,
            description="Knowledge base for insurance claims",
            enable_dynamic_field=True
        )

    def _create_indexes(self, collection: Collection) -> None:
        """Create indexes on collection."""
        vector_index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {
                "M": 16,
                "efConstruction": 200
            }
        }
        collection.create_index(
            field_name="embedding",
            index_params=vector_index_params
        )

        collection.create_index(
            field_name="doc_type",
            index_params={"index_type": "Trie"}
        )

    def create_collection(self) -> Collection:
        """Create knowledge base collection with schema."""
        schema = self._create_schema()

        collection = Collection(
            name=self._collection_name,
            schema=schema,
            using="default",
            shards_num=2
        )

        self._create_indexes(collection)
        return collection

    def _check_dimension_match(self, collection: Collection) -> bool:
        """Check if existing collection has correct dimension."""
        for field in collection.schema.fields:
            if field.name == "embedding":
                existing_dim = field.params.get("dim")
                return existing_dim == self._dimension
        return True

    def get_collection(self) -> Collection:
        """Get or create collection."""
        if self._collection is not None:
            return self._collection

        if utility.has_collection(self._collection_name):
            collection = Collection(self._collection_name)
            if not self._check_dimension_match(collection):
                print(
                    f"Collection has wrong dimension, "
                    f"recreating with {self._dimension}"
                )
                utility.drop_collection(self._collection_name)
                self._collection = self.create_collection()
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

        return self._format_search_results(results)

    def _format_search_results(
        self,
        results: List[Any]
    ) -> List[Dict[str, Any]]:
        """Format search results."""
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
            "collection_name": self._collection_name,
            "dimension": self._dimension
        }
