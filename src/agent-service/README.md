# Agent Service

Run-centric orchestration service for insurance claim processing, built with `LangGraph + LangChain` and refactored to a DeepAgent-style skill package layout.

## Runtime Summary

- Framework: FastAPI (`uvicorn main:app`)
- Default container port: `8000` (host mapped to `8003` in `docker-compose`)
- Workflow engine: LangGraph state machine (`workflow/graph.py`)
- Model/tool orchestration: LangChain-based client (`core/llm/client.py`)
- Metadata + interrupt persistence: Redis (`core/storage/redis_storage.py`)

## API v2 Contract (Breaking)

All orchestration endpoints are mounted under `/api/v2`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v2/runs` | Create run |
| `GET` | `/api/v2/runs/{run_id}` | Poll run status + interrupts + output |
| `POST` | `/api/v2/runs/{run_id}/resume` | Submit HITL decisions and resume |
| `GET` | `/api/v2/health` | API runtime health |
| `GET` | `/health` | Service health + Redis connectivity |

### Run Identity

- `run_id`: technical identity (primary key for all orchestration calls)
- `claim_id`: business metadata only

### Run Lifecycle

`created -> running -> interrupted -> running -> completed`  
or `created -> running -> failed`

### HITL Interrupt Contract

Each interrupt item includes:

- `interrupt_id`
- `run_id`
- `stage`
- `action`
- `payload`
- `allowed_decisions`

Resume payload accepts `decisions[]` with:

- `interrupt_id`
- `decision` (`approve | edit | reject`)
- optional `comment`
- optional `edited_payload` (required when decision is `edit`)

## Architecture

### Core Layers

1. Skill Catalog: DeepAgent-style packages in `skills/*` with `SKILL.md` + `skill.yaml`.
2. Execution Engine: LangGraph compiled graph + Redis-backed run metadata.
3. HITL Decision Engine: interrupt generation, decision validation, state update mapping.

### Skill Packaging

- Skill metadata is loaded from `skills/*/skill.yaml` first.
- `ConfigLoader` falls back to legacy `features/*/config` for compatibility.
- Current boundaries:
  - `completeness`
  - `quality`
  - `decision`
  - `policy_retrieval`
  - `document_extraction`

## Project Structure

```text
src/agent-service/
├── main.py
├── config.py
├── interfaces/
│   ├── api/
│   │   ├── models.py              # v2 run-based request/response types
│   │   └── routes.py              # /api/v2/runs orchestration API
│   └── web/
│       ├── app.py                 # Streamlit app entry
│       ├── api_client.py          # v2 run API client
│       ├── processing.py          # submit/poll helpers
│       ├── render_human_review.py # interrupt-driven HITL UI
│       ├── render_results.py      # final output dashboard
│       └── result_utils.py        # output normalization adapters
├── workflow/
│   ├── graph.py
│   ├── router.py
│   └── state.py
├── core/
│   ├── config/loader.py
│   ├── llm/client.py
│   └── storage/redis_storage.py
├── features/
│   ├── completeness/
│   ├── quality/
│   ├── decision/
│   └── orchestration/
└── skills/
    ├── completeness/
    ├── quality/
    ├── decision/
    ├── policy_retrieval/
    └── document_extraction/
```

## Local Development

```bash
cd src/agent-service
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

Run Streamlit UI:

```bash
cd src/agent-service
streamlit run interfaces/web/app.py
```

## Tests

```bash
cd src/agent-service
pytest tests/
```
