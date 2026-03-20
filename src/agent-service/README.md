# Agent Service

Multi-agent AI system for insurance claim processing using LangGraph and Google Gemini.

## Overview

The Agent Service orchestrates three specialized AI agents to process insurance claims through a multi-stage verification pipeline:

1. **Completeness Agent** - Verifies document completeness
2. **Quality Agent** - Validates medical quality and compliance
3. **Decision Agent** - Makes final claim decisions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Workflow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                   │
│  │ completeness_    │───▶│ quality_check   │                   │
│  │ check           │    │                 │                   │
│  └────────┬────────┘    └────────┬────────┘                   │
│           │                       │                              │
│           ▼                       ▼                              │
│  ┌─────────────────────────────────────────┐                   │
│  │           human_review (interrupt)        │                   │
│  └────────┬────────────────────────────────┘                   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ final_decision  │──────────▶ END                             │
│  └─────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Routing Logic

| After Completeness | → | quality_check (accept) / human_review (soft issues) / final_decision (hard reject) |
| After Quality | → | final_decision (accept/reject) / human_review (soft issues) |
| After Human Review | → | quality_check (edit) / end (approve/reject) |

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
│   ├── validate-diagnosis/
│   ├── validate-medication/
│   ├── check-icd/
│   ├── check-exclusion/
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
- **Conditional Routing**: Agent results determine next steps

## Prerequisites

- Python 3.11+
- MongoDB (for medicine database)
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
STRICT_SKILL_LOADING=false
```

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

### POST /api/v2/workflows/run

Start a new claim processing workflow.

**Request:**
```json
{
  "claim_id": "CLM-001",
  "policy_number": "POL-123",
  "input_file": "/path/to/document.pdf",
  "extracted_documents": {
    "diagnosis": "Pneumonia",
    "medications": ["Amoxicillin"]
  }
}
```

**Response:**
```json
{
  "run_id": "uuid-xxx",
  "claim_id": "CLM-001",
  "final_result": {"decision": "accept"},
  "current_step": "final_decision",
  "pending_human_review": false,
  "history": [...]
}
```

### POST /api/v2/workflows/resume/{run_id}

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

### GET /api/v2/workflows/status/{run_id}

Get current workflow status from MongoDB.

**Response:**
```json
{
  "run_id": "uuid-xxx",
  "claim_id": "CLM-001",
  "current_step": "human_review",
  "pending_human_review": true,
  "agent_1_result": {...},
  "agent_2_result": {...},
  "history": [...]
}
```

### GET /api/v2/health

Health check endpoint.

## Testing

```bash
# All tests
pytest tests/

# Single test file
pytest tests/test_validate_diagnosis.py

# Single test function
pytest tests/test_validate_diagnosis.py::TestValidateDiagnosisTool::test_tool_name

# With strict skill loading
STRICT_SKILL_LOADING=true pytest tests/
```

### Test Structure

| File | Tests |
|------|-------|
| `test_registry.py` | Skill loader discovery, caching, context injection |
| `test_routing.py` | Routing functions, decision logic |
| `test_validate_diagnosis.py` | Tool invocation, integration |

## Project Structure

```
src/agent-service/
├── agents/                    # Agent factories
│   └── factory.py            # All AgentFactory classes
├── api/                       # REST API
│   └── routes.py             # FastAPI routes
├── graphs/                    # LangGraph workflow
│   ├── claim_workflow.py     # Graph builder
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
├── tests/                     # Test suite
├── prompts/                    # System prompts
├── config.py                  # Settings
├── main.py                    # FastAPI app
└── llm_client.py             # Gemini client
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
| langgraph-checkpointing[mongodb] | ≥2.0.0 | MongoDB state persistence |
| langchain-core | ≥0.3.0 | Tool definitions |
| langchain-google-genai | ≥1.0.0 | Gemini LLM |
| fastapi | ≥0.109.0 | REST API |
| motor | ≥3.3.2 | Async MongoDB |
| structlog | ≥24.1.0 | Structured logging |
| pydantic | ≥2.5.3 | Data validation |
| streamlit | ≥1.28.0 | Web UI |
| requests | ≥2.31.0 | HTTP client |

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
    "should_continue": bool,           # Continue flag
    "error": str,                     # Error message
    "pending_human_review": bool,     # Waiting for human
}
```

## License

MIT
