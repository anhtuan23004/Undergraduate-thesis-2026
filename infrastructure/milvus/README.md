# Milvus Vector Database Infrastructure

Milvus 2.3.6 for semantic search and vector storage.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Etcd     │────▶│   Milvus    │◀────│    MinIO    │
│  (Metadata) │     │  (Vectors)  │     │  (Storage)  │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │    Attu     │
                     │   (Web UI)  │
                     └─────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Milvus | 19530 | Vector database API |
| Milvus (metrics) | 9091 | Prometheus metrics |
| Etcd | 2379 | Metadata storage |
| MinIO | 9000 | Object storage |
| MinIO (console) | 9001 | MinIO web UI |
| Attu | 8000 | Milvus web UI |

## Collection Schema

### knowledge_base

```python
{
    "id": VARCHAR (primary key),
    "content": VARCHAR (text content),
    "embedding": FLOAT_VECTOR (1536 dimensions),
    "metadata": JSON (additional info),
    "doc_type": VARCHAR (document type),
    "parent_id": VARCHAR (parent chunk id)
}
```

### Index Configuration

- **Type**: HNSW
- **Metric**: COSINE
- **M**: 16
- **efConstruction**: 200

## Quick Start

```bash
docker-compose -f infrastructure/milvus/docker-compose.yml up -d
```

## Access

```bash
# Attu Web UI
open http://localhost:8000

# MinIO Console
open http://localhost:9001
# Username: minioadmin
# Password: minioadmin
```

## Python Client

```python
from pymilvus import connections, Collection

# Connect
connections.connect(host="localhost", port=19530)

# Get collection
collection = Collection("knowledge_base")

# Search
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=5
)
```
