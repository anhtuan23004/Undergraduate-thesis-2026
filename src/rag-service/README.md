# RAG Service

Retrieval-Augmented Generation service with hybrid search (BM25 + Vector) using **Google Gemini embeddings**.

## Features

- **Hybrid Search**: Combine BM25 keyword search with vector similarity using RRF fusion
- **Gemini Embeddings**: Uses `gemini-embedding-001` (3072 dimensions)
- **RRF Fusion**: Reciprocal Rank Fusion for optimal result ranking
- **Parent-Child Chunking**: Hierarchical document chunking for better context
- **Milvus Vector DB**: HNSW index for fast similarity search
- **MongoDB**: Document metadata and content storage

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/search` | POST | Hybrid search (BM25 + Vector) |
| `/api/v1/rag/query` | POST | RAG query with context |
| `/api/v1/ingest` | POST | Ingest document with Gemini embeddings |

## Quick Start

### Prerequisites

- MongoDB running (port 27017)
- Milvus running (port 19530)
- **Google Gemini API Key** (get from https://makersuite.google.com/app/apikey)

### 1. Install Dependencies

```bash
cd src/rag-service
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your GEMINI_API_KEY
```

Required variables:
```bash
GEMINI_API_KEY=your_gemini_key_here
MONGODB_URL=mongodb://claims_app:claims_password@localhost:27017/claims
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DIM=3072  # Gemini embedding dimension
```

### 3. Run Service

```bash
# Development
uvicorn app.main:app --reload --port 8002

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

## Usage Examples

### Ingest Document (with Gemini Embeddings)

```bash
curl -X POST http://localhost:8002/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Health insurance policy for employees. Annual deductible is $500. Coverage includes hospital stays, doctor visits, and prescription medications.",
    "doc_type": "insurance_policies",
    "metadata": {
      "source": "policy_v1.pdf",
      "policy_number": "POL-001"
    }
  }'
```

**Response:**
```json
{
  "doc_id": "abc123def456",
  "chunks_created": 3,
  "status": "success"
}
```

### Hybrid Search

```bash
curl -X POST http://localhost:8002/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the deductible amount?",
    "top_k": 5,
    "doc_types": ["insurance_policies"]
  }'
```

**Response:**
```json
{
  "query": "What is the deductible amount?",
  "results": [
    {
      "id": "123456789",
      "content": "Annual deductible is $500...",
      "score": 0.85,
      "doc_type": "insurance_policies",
      "metadata": {"policy_number": "POL-001"},
      "sources": ["vector", "bm25"]
    }
  ],
  "total_results": 1,
  "search_time_ms": 245
}
```

### RAG Query

```bash
curl -X POST http://localhost:8002/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the deductible?",
    "policy_number": "POL-001"
  }'
```

## Hybrid Search Algorithm

### BM25 + Vector + RRF

```
BM25 Score: score_bm25 = Σ(IDF * (f * (k1 + 1)) / (f + k1 * (1 - b + b * (doc_len / avg_len))))

Vector Score: score_vector = cosine_similarity(query_embedding, doc_embedding)

RRF Fusion: score_rrf = Σ(1 / (k + rank))
  where k = 60 (constant)
```

### Embedding Model

- **Model**: `gemini-embedding-001`
- **Dimensions**: 3072
- **Task Type**: `RETRIEVAL_DOCUMENT` for ingestion, `RETRIEVAL_QUERY` for search

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | **Required** Gemini API key | - |
| `MONGODB_URL` | MongoDB connection string | Required |
| `MILVUS_HOST` | Milvus server host | localhost |
| `MILVUS_PORT` | Milvus server port | 19530 |
| `MILVUS_COLLECTION` | Collection name | insurance_kb_v2 |
| `MILVUS_DIM` | Embedding dimension | 3072 |
| `GEMINI_EMBEDDING_MODEL` | Gemini model | gemini-embedding-001 |
| `BM25_K1` | BM25 k1 parameter | 1.5 |
| `BM25_B` | BM25 b parameter | 0.75 |
| `RRF_K` | RRF constant | 60 |

## Project Structure

```
.
├── api/
│   └── routes/
│       ├── search.py      # Search endpoints
│       ├── query.py       # RAG query endpoints
│       └── ingest.py      # Ingestion endpoints
├── app/
│   └── config.py          # Configuration
├── core/
│   ├── embeddings/        # Gemini embedding generation
│   ├── search/            # BM25 + Hybrid search
│   └── chunking/          # Document chunking
└── db/
    └── milvus_client.py   # Milvus operations
```

## Collection Management

The service automatically handles Milvus collection dimension mismatches:
- If an existing collection has wrong dimension (e.g., 1536 from old OpenAI embeddings), it will be dropped and recreated with 3072 dimensions
- Collection name: `insurance_kb_v2`

## Data Flow

```
1. Ingest Request
   ↓
2. Chunk Document (parent-child)
   ↓
3. Generate Embeddings (Gemini, 3072 dims)
   ↓
4. Store in Milvus (vectors) + MongoDB (metadata)

Search Query
   ↓
1. Generate Query Embedding (Gemini)
   ↓
2. Vector Search (Milvus)
   ↓
3. BM25 Search (MongoDB)
   ↓
4. RRF Fusion
   ↓
5. Return Results
```
