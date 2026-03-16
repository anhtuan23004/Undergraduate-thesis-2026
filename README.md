# Agentic AI Insurance Claims Processing System

Multi-service system for automated health insurance claim processing.

## Runtime Topology

| Service | Host Port | Container Port | Notes |
|---|---:|---:|---|
| OCR Service | `8001` | `8000` | Gemini OCR extraction |
| RAG Service | `8002` | `8000` | Hybrid retrieval (BM25 + vector) |
| Agent Service | `8003` | `8000` | LangGraph multi-agent workflow |
| MongoDB | `27017` | `27017` | Metadata + app data |
| Redis | `6379` | `6379` | Claim metadata and pending review state |
| Milvus | `19530` | `19530` | Vector database |
| Mongo Express | `8081` | `8081` | Mongo UI |
| Milvus Attu | `8000` | `3000` | Milvus UI |

## Data Flow

1. OCR extracts document content
2. RAG ingests/searches policy context
3. Agent service runs multi-agent decision workflow
4. Human review loop is triggered for interrupted cases

## Prerequisites

- Docker + Docker Compose
- `GEMINI_API_KEY` (required)

Optional:
- `OPENAI_API_KEY` (kept for backward compatibility in some components)
- Langfuse keys

## Quick Start (Docker)

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY

docker-compose up -d --build
```

Verify health:

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

## Core API Endpoints

### OCR

- `POST /api/v1/ocr/raw`
- `POST /api/v1/ocr/fields`

### RAG

- `POST /api/v1/ingest`
- `POST /api/v1/search`
- `POST /api/v1/rag/query`

### Agent (new runtime contract)

- `POST /api/v1/multi-agent/process`
- `GET /api/v1/multi-agent/status/{claim_id}`
- `GET /api/v1/multi-agent/pending-reviews`
- `POST /api/v1/multi-agent/submit-review/{claim_id}`
- `GET /api/v1/multi-agent/health`

## Local Development

### OCR Service

```bash
cd src/ocr-service
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8001
```

### RAG Service

```bash
cd src/rag-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

### Agent Service

```bash
cd src/agent-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

Optional Streamlit UI for Agent Service:

```bash
cd src/agent-service
streamlit run interfaces/web/app.py
```

## Repo Structure

```text
.
├── docker-compose.yml
├── src/
│   ├── ocr-service/
│   ├── rag-service/
│   └── agent-service/
├── infrastructure/
├── docs/
└── tests/
```

## Service Docs

- [OCR Service](src/ocr-service/README.md)
- [RAG Service](src/rag-service/README.md)
- [Agent Service](src/agent-service/README.md)
