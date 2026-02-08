# RAG Service

Retrieval-Augmented Generation service with hybrid search (BM25 + Vector) using Google Gemini embeddings.

## Overview

The RAG Service provides intelligent document retrieval and question answering capabilities for the insurance claims processing system. It combines traditional keyword search (BM25) with semantic vector search using Reciprocal Rank Fusion (RRF) to deliver highly relevant results.

This service is responsible for ingesting policy documents and other insurance-related content, then retrieving relevant context to support the Agent Service's decision-making process.

## Features

- Hybrid search combining BM25 keyword search with vector similarity
- Google Gemini embeddings (gemini-embedding-001, 3072 dimensions)
- Reciprocal Rank Fusion (RRF) for optimal result ranking
- Parent-child document chunking for better context preservation
- Milvus vector database with HNSW index for fast similarity search
- MongoDB for document metadata and content storage

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Ingest    │────▶│   Chunker   │────▶│   Gemini    │
│   Request   │     │  (Parent-   │     │ Embeddings  │
└─────────────┘     │   Child)    │     │  (3072d)    │
                    └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────┐
                    │                          │          │
                    ▼                          ▼          ▼
             ┌─────────────┐           ┌─────────────┐ ┌─────────────┐
             │   Milvus    │           │   MongoDB   │ │   MongoDB   │
             │  (Vectors)  │           │  (Metadata) │ │   (BM25)    │
             └─────────────┘           └─────────────┘ └─────────────┘
                                                          │
                    ┌─────────────────────────────────────┘
                    │
                    ▼
             ┌─────────────┐
             │    RRF      │
             │   Fusion    │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │   Results   │
             └─────────────┘
```

## Quick Start

### Prerequisites

- MongoDB running (port 27017)
- Milvus running (port 19530)
- Google Gemini API Key (get from https://makersuite.google.com/app/apikey)

### Setup

```bash
cd src/rag-service
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
GEMINI_API_KEY=your_gemini_key_here
MONGODB_URL=mongodb://claims_app:claims_password@localhost:27017/claims
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DIM=3072  # Gemini embedding dimension
```

### Run Service

```bash
# Development
uvicorn app.main:app --reload --port 8002

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Gemini API key (required) | - |
| `MONGODB_URL` | MongoDB connection string | Required |
| `MILVUS_HOST` | Milvus server host | `localhost` |
| `MILVUS_PORT` | Milvus server port | `19530` |
| `MILVUS_COLLECTION` | Collection name | `insurance_kb_v2` |
| `MILVUS_DIM` | Embedding dimension | `3072` |
| `GEMINI_EMBEDDING_MODEL` | Gemini model | `gemini-embedding-001` |
| `BM25_K1` | BM25 k1 parameter | `1.5` |
| `BM25_B` | BM25 b parameter | `0.75` |
| `RRF_K` | RRF constant | `60` |

## Usage

### Health Check

```bash
curl http://localhost:8002/health
```

### Ingest Document

**Endpoint:** `POST /api/v1/ingest`

Ingest a document with Gemini embeddings for later retrieval.

**Example:**
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

**Endpoint:** `POST /api/v1/search`

Search documents using hybrid BM25 + Vector search with RRF fusion.

**Example:**
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

**Endpoint:** `POST /api/v1/rag/query`

Query with automatic context retrieval and response generation.

**Example:**
```bash
curl -X POST http://localhost:8002/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the deductible?",
    "policy_number": "POL-001"
  }'
```

## Development

### Project Structure

```
src/rag-service/
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
├── db/
│   └── milvus_client.py   # Milvus operations
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

### Hybrid Search Algorithm

#### BM25 + Vector + RRF

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

### Data Flow

**Ingestion:**
```
1. Ingest Request
   ↓
2. Chunk Document (parent-child)
   ↓
3. Generate Embeddings (Gemini, 3072 dims)
   ↓
4. Store in Milvus (vectors) + MongoDB (metadata)
```

**Search:**
```
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

## Troubleshooting

### Collection dimension mismatch

The service automatically handles Milvus collection dimension mismatches:
- If an existing collection has wrong dimension (e.g., 1536 from old OpenAI embeddings), it will be dropped and recreated with 3072 dimensions
- Collection name: `insurance_kb_v2`

### Connection errors

- Verify MongoDB is running on port 27017
- Verify Milvus is running on port 19530
- Check connection strings in `.env` file

### Embedding errors

- Verify `GEMINI_API_KEY` is set correctly
- Check that the API key has not expired
- Review logs for specific error messages

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8002/docs`
- **ReDoc**: `http://localhost:8002/redoc`
