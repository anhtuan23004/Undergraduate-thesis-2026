# Agentic AI Insurance Claims Processing System

Multi-service system for automated health insurance claim processing.

## Runtime Topology

| Service | Host Port | Container Port | Notes |
|---|---:|---:|---|
| OCR Service | `8001` | `8000` | Gemini OCR extraction |
| Agent Service | `8003` | `8000` | LangGraph multi-agent workflow |
| MongoDB | `27017` | `27017` | Metadata + app data |
| Mongo Express | `8081` | `8081` | Mongo UI |

## Data Flow

1. OCR extracts document content
2. Agent service runs multi-agent decision workflow
3. Human review loop is triggered for interrupted cases

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
curl http://localhost:8003/health
```

## Core API Endpoints

### OCR

- `POST /api/v1/ocr/raw`
- `POST /api/v1/ocr/fields`

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
│   └── agent-service/
├── infrastructure/
├── docs/
└── tests/
```

## Service Docs

- [OCR Service](src/ocr-service/README.md)
- [Agent Service](src/agent-service/README.md)
