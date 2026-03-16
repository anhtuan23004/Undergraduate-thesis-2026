# Agent Service

Multi-agent orchestration service for insurance claim processing.

## Runtime Summary

- Framework: FastAPI (`uvicorn main:app`)
- Default port: `8000` (host mapped to `8003` in Docker Compose)
- Workflow engine: LangGraph state graph
- LLM runtime: Gemini via `langchain-google-genai` (`core/llm/client.py`)
- External dependencies:
  - RAG Service (`RAG_SERVICE_URL`, default `http://rag-service:8000`)
  - OCR Service (`OCR_SERVICE_URL`, default `http://ocr-service:8000`)
  - Redis (`REDIS_URL`) for claim metadata / pending review / error state

## API Contract

All business endpoints are mounted under `/api/v1/multi-agent`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/multi-agent/process` | Start claim workflow in background |
| `GET` | `/api/v1/multi-agent/status/{claim_id}` | Poll current workflow status |
| `GET` | `/api/v1/multi-agent/pending-reviews` | List claims waiting for human review |
| `POST` | `/api/v1/multi-agent/submit-review/{claim_id}` | Submit human decision and resume graph |
| `GET` | `/api/v1/multi-agent/health` | Multi-agent sub-router health |
| `GET` | `/health` | Service health + Redis connectivity |

Status values from `GET /status/{claim_id}`:
- `starting`
- `running`
- `interrupted` (waiting for human review)
- `finished`
- `error`

## Architecture (Current)

### Workflow

1. Completeness agent
2. Quality agent
3. Human review interrupt node (when needed)
4. Final decision agent

### State Persistence

- LangGraph checkpoint: in-memory `MemorySaver` (process-local)
- Redis: persistent metadata for:
  - `claim_id -> thread_id` mapping
  - pending review queue
  - background task errors

Notes:
- Redis data uses TTL (`REDIS_TTL_SECONDS`, default 24h).
- Graph checkpoint itself is not durable across process restarts.

## Project Structure

```text
src/agent-service/
├── main.py                        # FastAPI app entrypoint
├── config.py                      # Pydantic settings
├── interfaces/
│   ├── api/
│   │   ├── models.py              # Request/response schemas
│   │   └── routes.py              # REST routes under /api/v1/multi-agent
│   └── web/
│       ├── app.py                 # Streamlit UI
│       ├── api_client.py          # UI HTTP client helpers
│       ├── constants.py           # UI endpoint/runtime constants
│       ├── processing.py          # UI orchestration (submit/poll)
│       ├── result_utils.py        # UI result normalization helpers
│       └── state.py               # UI session state helpers
├── workflow/
│   ├── graph.py                   # Graph builder
│   ├── router.py                  # Conditional routing
│   └── state.py                   # GraphState typed contract
├── core/
│   ├── llm/client.py              # Gemini LLM client
│   ├── config/loader.py           # Agent config loader
│   └── storage/redis_storage.py   # Redis metadata storage
└── features/
    ├── completeness/
    ├── quality/
    ├── decision/
    └── orchestration/
```

## Configuration

Primary environment variables:

```bash
# App
DEBUG=false
HOST=0.0.0.0
PORT=8000

# LLM (current runtime)
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
GEMINI_TEMPERATURE=0.3
GEMINI_MAX_TOKENS=8192

# Dependencies
RAG_SERVICE_URL=http://rag-service:8000
OCR_SERVICE_URL=http://ocr-service:8000
REDIS_URL=redis://redis:6379/0
REDIS_TTL_SECONDS=86400

# Data / observability
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=claims
LANGFUSE_HOST=http://localhost:3000
```

See [`src/agent-service/.env.example`](./.env.example) for full template.

## Run Locally (Dev)

```bash
cd src/agent-service
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

Streamlit UI (optional, same service directory):

```bash
cd src/agent-service
streamlit run interfaces/web/app.py
```

## Docker Runtime

In root compose (`docker-compose.yml`):
- container listens on `8000`
- host port mapped to `8003`

```bash
docker-compose up -d --build agent-service
curl http://localhost:8003/health
```

## Test

```bash
cd src/agent-service
pytest tests/
```
