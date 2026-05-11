# Agent Service

Multi-agent AI system for insurance claim processing using LangGraph and Google Gemini.

## Overview

The Agent Service orchestrates specialized AI agents to process insurance claims through a multi-stage verification pipeline:

1. **Completeness Agent** - Verifies document completeness
2. **Quality Agent** - Validates medical quality and compliance
3. **Verifier Agent** - Cross-checks agent assessments before auto-approval or escalation
4. **Decision Agent** - Makes final claim decisions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Workflow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  upload ─▶ OCR prepare/cache ─▶ initial GraphState              │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │ completeness_   │───▶│ agent_review    │                   │
│  │ check           │    │ verifier gate   │                   │
│  └─────────────────┘    └────────┬────────┘                   │
│                                  ▼                            │
│                         ┌─────────────────┐                   │
│                         │ quality_check   │                   │
│                         └────────┬────────┘                   │
│                                  ▼                            │
│                         ┌─────────────────┐                   │
│                         │ final_decision  │                   │
│                         └────────┬────────┘                   │
│                                  ▼                            │
│                         human_review / END                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Service Boundaries

Route handlers are intentionally thin:

| Module | Responsibility |
|--------|----------------|
| `api/workflows.py` | Run/resume/continue/stream endpoints and HTTP error mapping |
| `api/upload.py` | Multipart upload validation and storage |
| `api/status.py` | Workflow status and dependency-light API health |
| `api/sse.py` | Server-sent event formatting and graph event streaming |
| `services/graph_service.py` | Compiled graph singleton and MongoDB checkpointer setup |
| `services/ocr_service.py` | OCR cache lookup, OCR HTTP calls, and OCR audit records |
| `services/workflow_state.py` | Initial `GraphState` and standardized response shape |
| `services/file_policy.py` | Upload extension/MIME checks and safe `UPLOADS_DIR` path handling |
| `services/mongodb_config.py` | MongoDB URL normalization and explicit timeout settings |

### Routing Logic

The graph exposes explicit state fields so routing and UI do not depend on parsing `current_step`.

| Field | Values | Purpose |
|-------|--------|---------|
| `active_stage` | `completeness`, `quality`, `final`, `none` | Automated stage currently running |
| `review_stage` | `completeness`, `quality`, `final`, `none` | Stage being reviewed by verifier or human |
| `workflow_status` | `running`, `paused`, `waiting_human`, `completed`, `error` | Machine-readable lifecycle state |
| `ocr_stage` | `none`, `v1_document`, `phase1_classified`, `phase2_extracted`, `error` | OCR pipeline stage represented by `extracted_documents` |

| From | Route |
|------|-------|
| `completeness_check` | `agent_review` |
| `agent_review` after completeness auto-approval | `quality_check` |
| `agent_review` after quality auto-approval | `final_decision` |
| `agent_review` escalation | `human_review` |
| `human_review` approve/edit for completeness | `quality_check` |
| `human_review` approve/edit for quality | `final_decision` |
| `human_review` final decision or final reject | `END` |

## Skill-Based Tool System

All tools are organized in `skills/` directories with the following structure:

```
skills/
├── shared/                          # Shared across agents
│   └── classify-benefit/
│       ├── scripts/tool.py          # LangChain @tool
│       └── SKILL.md                # Tool instructions
├── completeness-agent/              # Completeness verification
│   ├── extract-documents/
│   ├── check-required-docs/
│   └── validate-consistency/
├── quality-agent/                   # Medical quality checks
│   ├── validate-medication/
│   ├── check-icd/
│   ├── check-exclusion/
│   ├── web-search/
│   └── search-medicine/
└── decision-agent/                  # Decision aggregation
    └── aggregate-issues/
```

### Tool Loading

Tools are dynamically loaded at runtime via `skill_loader.py`:

```python
from tools.skill_loader import load_agent_skills

tools, contexts = load_agent_skills("quality_agent")
# tools: List[StructuredTool]
# contexts: str (combined SKILL.md content)
```

## Features

- **Dynamic Tool Loading**: Tools loaded from `skills/` directories
- **Skill Contexts**: Each tool has `SKILL.md` for LLM instructions
- **Human-in-the-Loop**: Workflow interrupts for human review
- **State Persistence**: MongoDB checkpointer for long-running workflows
- **OCR Reuse**: OCR output is cached by file hash, OCR version, stage, and pipeline
- **Upload Guardrails**: Uploads are restricted by size, extension, MIME type, and safe path policy
- **Explicit Lifecycle Fields**: API responses expose `active_stage`, `review_stage`, and `workflow_status`
- **Conditional Routing**: Agent results determine next steps

## Prerequisites

- Python 3.11+
- MongoDB (workflow checkpoints, OCR audit records, medicine database)
- OCR service reachable through `OCR_SERVICE_URL`
- Google Gemini API key

## Installation

```bash
cd src/agent-service
pip install -r requirements.txt
```

### Environment Variables

Create `.env` file:

```env
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_TEMPERATURE=0.3
GEMINI_MAX_TOKENS=8192
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=claims
MONGODB_CONNECT_TIMEOUT_MS=5000
MONGODB_SERVER_SELECTION_TIMEOUT_MS=5000
MONGODB_SOCKET_TIMEOUT_MS=20000
OCR_SERVICE_URL=http://localhost:8091
OCR_API_VERSION=v2
OCR_TIMEOUT=120
OUTBOUND_HTTP_CONNECT_TIMEOUT=10
UPLOADS_DIR=./uploads
MAX_UPLOAD_SIZE_MB=20
ALLOWED_ORIGINS=http://localhost:8501
STRICT_SKILL_LOADING=false
```

Startup validation is strict when `DEBUG=false`: `GEMINI_API_KEY`, `MONGODB_URL`, and `OCR_SERVICE_URL` must be set. Empty `ALLOWED_ORIGINS` defaults to `[]` in non-debug mode and `["*"]` only when `DEBUG=true`.

## Running

### Development

```bash
uvicorn main:app --reload --port 8003
```

### Production

```bash
uvicorn main:app --host 0.0.0.0 --port 8003
```

### Docker

```bash
docker-compose up agent-service
```

## API Endpoints

### POST /api/v1/workflows/run

Start a new claim processing workflow.

**Request:**

```json
{
  "claim_id": "CLM-001",
  "policy_number": "POL-123",
  "input_file": "uploaded-document.pdf",
  "file_hash": "optional-sha256"
}
```

`input_file` must resolve inside `UPLOADS_DIR`. The common UI flow is to call `/api/v1/workflows/upload` first, then pass the returned `file_path` and `file_hash` into `/api/v1/workflows/run` or `/api/v1/workflows/run-stream`.

**Response:**

```json
{
  "run_id": "uuid-xxx",
  "claim_id": "CLM-001",
  "final_result": {"decision": "approve"},
  "current_step": "final_decision_complete",
  "active_stage": "none",
  "review_stage": "none",
  "workflow_status": "completed",
  "pending_human_review": false,
  "paused": false,
  "pause_at": null,
  "history": [...]
}
```

### POST /api/v1/workflows/upload

Upload a claim document and return a server-side file path for workflow usage.

Allowed extensions: `.pdf`, `.png`, `.jpg`, `.jpeg`.
Allowed MIME types: `application/pdf`, `image/png`, `image/jpeg`.
Maximum size is configured with `MAX_UPLOAD_SIZE_MB`.

**Response:**

```json
{
  "filename": "claim.pdf",
  "file_path": "/absolute/path/inside/uploads/uuid_claim.pdf",
  "size_bytes": 123456,
  "file_hash": "sha256-hex"
}
```

### POST /api/v1/workflows/run-stream

Start a workflow and stream progress with server-sent events. Events include `run_started`, `node_start`, `node_end`, `done`, and `error`.

### POST /api/v1/workflows/resume/{run_id}

Resume a workflow after human review decision.

**Request:**

```json
{
  "decision": "approve",
  "notes": "Reviewed and approved"
}
```

For edit decisions:

```json
{
  "decision": "edit",
  "notes": "Please verify diagnosis",
  "edited_result": {"source": "agent_2", "valid": true, "issues": []}
}
```

### GET /api/v1/workflows/status/{run_id}

Get current workflow status from MongoDB.

**Response:**

```json
{
  "run_id": "uuid-xxx",
  "claim_id": "CLM-001",
  "current_step": "human_review",
  "active_stage": "none",
  "review_stage": "quality",
  "workflow_status": "waiting_human",
  "pending_human_review": true,
  "paused": true,
  "pause_at": "human_review",
  "agent_1_result": {...},
  "agent_2_result": {...},
  "human_review_result": null,
  "history": [...]
}
```

### POST /api/v1/workflows/continue/{run_id}

Continue a graph paused at a non-human-review node.

### GET /api/v1/health

Health check endpoint.

## Testing

```bash
# All agent-service tests
python -m pytest src/agent-service/tests -q

# P7 lifecycle/config/upload/OCR checks
python -m pytest \
  src/agent-service/tests/test_config_lifecycle.py \
  src/agent-service/tests/test_upload_policy.py \
  src/agent-service/tests/test_ocr_service.py \
  src/agent-service/tests/test_api_status.py \
  -q

# Lint
python -m ruff check src/agent-service

# With strict skill loading
STRICT_SKILL_LOADING=true python -m pytest src/agent-service/tests -q
```

### Test Structure

| Category | Files | Purpose |
|----------|-------|---------|
| Unit | `test_routing.py`, `test_agent_review.py`, `test_agent_prompt_builders.py`, `test_agent_output_parsing.py` | Routing, verifier constraints, prompt builders, parsing |
| Contract | `test_api_schemas.py`, `test_api_status.py`, `test_human_review.py` | API schemas, error payloads, human review contract |
| Lifecycle/P7 | `test_config_lifecycle.py`, `test_upload_policy.py`, `test_ocr_service.py` | Startup validation, upload guardrails, safe paths, OCR timeout/cache behavior |
| Skill loader/tools | `test_registry.py`, `test_agent_skill_discovery.py`, `test_web_search_tool.py` | Skill discovery, duplicate tool guard, optional tool behavior |
| Regression | `test_workflow_state.py`, `test_ocr_extraction.py` | Response shape, initial state, OCR phase transitions |

## Project Structure

```
src/agent-service/
├── agents/                    # Agent factories
│   ├── audit.py              # Agent audit logging
│   ├── factory.py            # AgentFactory classes
│   ├── output_parsing.py     # LLM output parsing helpers
│   └── prompt_builders.py    # Per-agent prompt builders
├── api/                       # REST API
│   ├── routes.py             # Router composition
│   ├── workflows.py          # Workflow endpoints
│   ├── upload.py             # Upload endpoint
│   ├── status.py             # Status and health endpoints
│   └── sse.py                # Server-sent events
├── graphs/                    # LangGraph workflow
│   ├── claim_workflow.py     # Graph builder
│   ├── constants.py          # Node/stage/status constants
│   ├── ocr_extraction.py     # OCR phase 2 graph node
│   ├── routing.py            # Conditional routing
│   ├── state.py              # GraphState schema
│   └── human_review.py       # Human review node
├── interfaces/
│   └── web/
│       ├── app.py            # Streamlit UI
│       └── README.md         # UI documentation
├── skills/                    # Tool implementations
│   ├── completeness-agent/
│   ├── quality-agent/
│   ├── decision-agent/
│   └── shared/
├── tools/                     # Tool infrastructure
│   └── skill_loader.py       # Dynamic loader
├── services/                  # Non-route business services
│   ├── file_policy.py        # Upload/path guardrails
│   ├── graph_service.py      # Compiled graph lifecycle
│   ├── mongodb_config.py     # Mongo URL/timeout helpers
│   ├── ocr_service.py        # OCR cache/calls/audit
│   └── workflow_state.py     # State/response builders
├── tests/                     # Test suite
├── prompts/                    # System prompts
├── config.py                  # Settings
├── main.py                    # FastAPI app
└── agent.py               # Gemini client
```

## Key Files

| File | Purpose |
|------|---------|
| `factory.py` | Creates agent nodes with tools and prompts |
| `skill_loader.py` | Dynamically loads tools + SKILL.md |
| `claim_workflow.py` | Builds LangGraph with routing |
| `routing.py` | Conditional edge logic |
| `state.py` | GraphState TypedDict definition |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| langgraph | ≥0.0.50 | Agent orchestration |
| langgraph-checkpoint-mongodb | ≥0.1.0 | MongoDB state persistence |
| langchain-core | ≥0.3.0 | Tool definitions |
| langchain-google-genai | ≥1.0.0 | Gemini LLM |
| fastapi | ≥0.109.0 | REST API |
| motor | ≥3.3.2 | Async MongoDB |
| structlog | ≥24.1.0 | Structured logging |
| pydantic | ≥2.5.3 | Data validation |
| streamlit | ≥1.28.0 | Web UI |
| requests | ≥2.31.0 | HTTP client |
| python-multipart | ≥0.0.9 | Multipart upload handling |
| tavily-python | ≥0.3.3 | Optional web search fallback |

## Web Interface

Interactive UI for demo at `interfaces/web/app.py`.

```bash
# Start agent service
uvicorn main:app --reload --port 8003

# Start Streamlit UI (in another terminal)
cd interfaces/web
streamlit run app.py --server.port 8501
```

Features:

- Session management with run history
- Claim input form
- Workflow status dashboard
- Human-in-the-Loop review panel
- Developer mode (raw GraphState viewer)

## Development

### Code Style

- Python 3.11+
- Type hints required
- Use `structlog` for logging
- Docstrings for all public functions

### Adding New Tools

1. Create directory in appropriate agent's skills folder:

   ```
   skills/quality-agent/my-new-tool/
   ├── scripts/
   │   ├── __init__.py
   │   └── tool.py
   └── SKILL.md
   ```

2. Implement tool using `@tool` decorator:

   ```python
   from langchain_core.tools import tool

   @tool
   def my_new_tool(input: str) -> str:
       """Description for LLM."""
       return json.dumps({"result": "value"})
   ```

3. Add `SKILL.md` with role/workflow instructions

Tool is auto-discovered on next restart.

## Workflow States

```python
GraphState = {
    "run_id": str,                    # Unique run identifier
    "claim_id": str,                  # Claim number
    "policy_number": str,             # Policy number
    "input_file": str,                # Document path
    "extracted_documents": dict,     # OCR data
    "agent_1_result": dict,           # Completeness result
    "agent_2_result": dict,           # Quality result
    "human_review_result": dict,      # Human decision
    "edited_agent_1_result": dict,    # Edited completeness
    "edited_agent_2_result": dict,     # Edited quality
    "final_result": dict,             # Final decision
    "history": list,                  # All agent invocations
    "current_step": str,              # Current node
    "active_stage": str,              # completeness | quality | final | none
    "review_stage": str,              # completeness | quality | final | none
    "workflow_status": str,           # running | paused | waiting_human | completed | error
    "ocr_stage": str,                 # none | v1_document | phase1_classified | phase2_extracted | error
    "should_continue": bool,           # Continue flag
    "error": str,                     # Error message
    "pending_human_review": bool,     # Waiting for human
}
```

## Prompt Budget Strategy

Prompt construction lives in `agents/prompt_builders.py`. The current strategy is to send each agent only the state needed for its decision where implemented:

- Completeness focuses on document inventory and administrative claim fields.
- Quality focuses on diagnosis, ICD, medication, treatment, amount, and medical evidence.
- Decision receives agent results and issue summaries instead of raw OCR.
- Verifier receives the primary assessment plus related evidence where available.

Prompt budget enforcement and truncation tests are tracked in `plan.md` under P2/P8 and should be completed before adding more tools or agents.

## License

MIT
