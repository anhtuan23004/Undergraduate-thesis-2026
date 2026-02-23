# Agent Service

Multi-agent AI workflow for automated health insurance claims processing using LangGraph and OpenAI.

## Overview

The Agent Service orchestrates a **multi-agent workflow** that evaluates insurance claims through sequential validation stages. Each claim passes through a completeness check, a quality/medical validation check, an optional human review loop, and a final decision node — all managed as a compiled LangGraph `StateGraph`.

## Architecture

```
Input (claim_id, input_file, policy_number)
          │
          ▼
┌─────────────────┐
│ Completeness    │──── reject ──────────────────┐
│ Check (Agent 1) │                              │
└────────┬────────┘                              │
         │ accept            accept_with_edit    │
         ▼                        ▼              │
┌─────────────────┐     ┌──────────────────┐    │
│ Quality Check   │     │ Human Review     │    │
│ (Agent 2)       │     │                  │    │
└────────┬────────┘     └────────┬─────────┘    │
         │                       │              │
    accept/reject           approve/reject      │
         │                  edit (loop back)    │
         └──────────────────────┘              │
                        │                      │
                        ▼                      ▼
               ┌─────────────────────────────────┐
               │       Final Decision             │
               └─────────────────┬───────────────┘
                                 │
                                END
```

### Nodes

| Node | Description |
|------|-------------|
| `completeness_check` | Agent 1 — Validates that all required documents are present and the claim is complete |
| `quality_check` | Agent 2 — Validates medical consistency, diagnosis codes, medications, and benefit eligibility |
| `human_review` | Human-in-the-loop node for edge cases requiring manual review |
| `final_decision` | Aggregates all agent results and emits the final APPROVE/REJECT/PENDING decision |

### Routing Logic

| From | Decision | Next Node |
|------|----------|-----------|
| `completeness_check` | `accept` | `quality_check` |
| `completeness_check` | `reject` | `final_decision` |
| `completeness_check` | `accept_with_edit` | `human_review` |
| `quality_check` | `accept` or `reject` | `final_decision` |
| `quality_check` | `accept_with_edit` | `human_review` |
| `human_review` | `approve` or `reject` | `final_decision` |
| `human_review` | `edit` | `quality_check` *(loop back)* |

## Tools

Each agent uses a set of structured tools that follow the OpenAI function-calling schema via `BaseTool`.

| Tool | Description |
|------|-------------|
| `ExtractDocumentsTool` | Extracts structured data from input files via OCR service |
| `CheckRequiredDocumentsTool` | Confirms all mandatory claim documents are present |
| `ClassifyBenefitTool` | Classifies the benefit type (inpatient, outpatient, etc.) |
| `ValidateConsistencyTool` | Cross-checks fields for logical consistency |
| `ValidateDiagnosisTool` | Validates ICD-10 diagnosis codes |
| `CheckExclusionTool` | Flags conditions excluded by the policy |
| `ValidateMedicationTool` | Verifies prescribed medications against diagnosis |
| `AggregateIssuesTool` | Collects and prioritizes all issues for the final decision |

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key
- RAG Service running (port 8002)

### Setup

```bash
cd src/agent-service
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```env
# Required
OPENAI_API_KEY=sk-your_openai_key_here

# Optional (defaults shown)
RAG_SERVICE_URL=http://rag-service:8000
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

### Run Service

```bash
uvicorn app.main:app --reload --port 8003
```

## API Reference

### `POST /api/v1/multi-agent/process`

Process a claim through the full multi-agent workflow.

**Request body:**

```json
{
  "claim_id": "CLM-001",
  "input_file": "/path/to/claim_file.pdf",
  "policy_number": "POL-001"
}
```

**Response:**

```json
{
  "claim_id": "CLM-001",
  "final_decision": "APPROVE",
  "agent_1_result": {
    "decision": "accept",
    "confidence": 0.95,
    "reasoning": "All required documents are present.",
    "missing_documents": [],
    "issues": []
  },
  "agent_2_result": {
    "decision": "accept",
    "confidence": 0.88,
    "reasoning": "Diagnosis and medications are consistent.",
    "issues": []
  },
  "human_review_result": null,
  "processing_steps": [...]
}
```

**Possible `final_decision` values:** `APPROVE` · `REJECT` · `PENDING`

**Possible `agent_1_result.decision` / `agent_2_result.decision` values:** `accept` · `reject` · `accept_with_edit`

---

### `GET /health`

```bash
curl http://localhost:8003/health
# {"status": "healthy"}
```

### `GET /api/v1/multi-agent/health`

```bash
curl http://localhost:8003/api/v1/multi-agent/health
# {"status": "healthy", "service": "multi-agent"}
```

### `GET /`

Returns service metadata and available endpoints.

---

Interactive API docs available at:
- **Swagger UI**: `http://localhost:8003/docs`
- **ReDoc**: `http://localhost:8003/redoc`

## Project Structure

```
src/agent-service/
├── api/
│   ├── models.py          # Pydantic request/response models
│   └── routes.py          # API endpoints
├── app/
│   ├── config.py          # Settings (pydantic-settings)
│   └── main.py            # FastAPI application & lifespan
├── core/
│   ├── graph.py           # LangGraph StateGraph builder
│   ├── router.py          # Conditional routing functions
│   └── state.py           # GraphState TypedDict
├── agents/                # Agent node implementations
│   ├── completeness_agent.py
│   ├── quality_agent.py
│   ├── human_review.py
│   └── final_agent.py
├── tools/                 # BaseTool + 8 concrete tool implementations
│   ├── base.py
│   ├── extract_documents.py
│   ├── check_required_documents.py
│   ├── classify_benefit.py
│   ├── validate_consistency.py
│   ├── validate_diagnosis.py
│   ├── check_exclusion.py
│   ├── validate_medication.py
│   └── aggregate_issues.py
└── requirements.txt
```

## State Schema

`GraphState` (TypedDict) is passed between all nodes:

```python
{
  # Input
  "input_file": str,              # Path to the claim file
  "extracted_documents": dict,    # OCR-extracted document data

  # Agent results
  "agent_1_result": dict | None,  # Completeness check result
  "agent_2_result": dict | None,  # Quality check result
  "human_review_result": dict | None,

  # Output
  "final_result": dict | None,    # Aggregated final decision

  # Control
  "history": list,                # Full workflow audit trail (append-only)
  "current_step": str,            # Current node name
  "should_continue": bool,        # Halt flag
  "error": str | None             # Error message on failure
}
```

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | **Required** |
| `RAG_SERVICE_URL` | RAG service base URL | `http://rag-service:8000` |
| `HOST` | Bind host | `0.0.0.0` |
| `PORT` | Bind port | `8000` |
| `DEBUG` | Enable hot-reload | `false` |

## Troubleshooting

**`OPENAI_API_KEY` not set**
- Ensure `.env` exists and is loaded. The service will fail to start without this key.

**RAG service unavailable**
- Verify RAG service is running at the configured `RAG_SERVICE_URL`.
- Check Docker network if running inside containers.

**500 error on `/multi-agent/process`**
- Check the `error` field in the response body.
- Review structured logs output by `structlog` for the full trace.
