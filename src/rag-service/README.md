# RAG Service

Retrieval-Augmented Generation service for insurance policy knowledge.

## Runtime Summary

- Framework: FastAPI (`uvicorn app.main:app`)
- Default port: `8000` (host mapped to `8002` in Docker Compose)
- Retrieval strategy: Hybrid `BM25 + vector` with `RRF`
- Embeddings: Gemini (`gemini-embedding-001`, default 3072 dims)
- Storage:
  - Milvus for vectors
  - MongoDB for documents/metadata and BM25 corpus

## API Endpoints

All routes use `/api/v1` prefix.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/ingest` | Ingest documents into hybrid index |
| `POST` | `/api/v1/search` | Hybrid retrieval |
| `POST` | `/api/v1/rag/query` | Retrieval + generation style response |
| `GET` | `/health` | Service health |

## Configuration

```bash
# App
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=insurance_kb_v2
MILVUS_DIM=3072

# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=claims

# Gemini embeddings
GEMINI_API_KEY=...
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Search tuning
BM25_K1=1.5
BM25_B=0.75
TOP_K=5
RRF_K=60
```

See [`src/rag-service/.env.example`](./.env.example) for full template.

## Run Locally

```bash
cd src/rag-service
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

## Docker Runtime

In root compose (`docker-compose.yml`):
- container port `8000`
- host port `8002`

```bash
docker-compose up -d --build rag-service
curl http://localhost:8002/health
```

## Quick API Examples

```bash
# Ingest
curl -X POST http://localhost:8002/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"content":"Policy text...","doc_type":"insurance_policies","metadata":{"policy_number":"POL-001"}}'

# Search
curl -X POST http://localhost:8002/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"deductible amount","top_k":5}'
```
