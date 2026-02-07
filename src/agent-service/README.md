# Agent Service

ReAct-based AI agent for insurance claim decision-making using LangGraph and OpenAI.

**Port**: 8003

## Features

- **ReAct Loop**: Reasoning + Acting framework
- **Tool System**: Extensible tool registry
- **State Persistence**: MongoDB checkpointing
- **Structured Output**: JSON decision format
- **LangGraph**: Modern agent framework

## ReAct Architecture

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Observe │───▶│  Think  │───▶│   Act   │───▶│ Reflect │───▶│ Decide  │
│         │    │         │    │ (Tool)  │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘    └─────────┘
                                                   │
                                              (loop if needed)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/agent/decide` | POST | Process claim and make decision |
| `/api/v1/agent/graph` | GET | Get graph structure |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with OPENAI_API_KEY

# Run service
uvicorn app.main:app --reload --port 8003
```

## Usage Example

```bash
curl -X POST http://localhost:8003/api/v1/agent/decide \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "CLM-001",
    "extracted_data": {
      "patient": "Nguyễn Văn A",
      "diagnosis_codes": ["J18.9"],
      "total_amount": 15500000,
      "hospital": "Bệnh viện Chợ Rẫy"
    },
    "policy_number": "POL-001"
  }'
```

## Response Format

```json
{
  "claim_id": "CLM-001",
  "decision": "APPROVE",
  "confidence_score": 0.92,
  "amount_recommended": 14500000,
  "reasoning": "Based on policy review...",
  "evidence": [...],
  "risks": [...],
  "iterations": 3
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `icd_lookup` | Validate ICD-10 diagnosis codes |
| `policy_check` | Check policy terms and coverage |
| `coverage_calc` | Calculate eligible claim amounts |
| `document_query` | Query extracted document fields |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | Model name | gpt-4 |
| `MONGODB_URL` | MongoDB connection | Required |
| `MAX_ITERATIONS` | Max ReAct iterations | 10 |
| `CONFIDENCE_THRESHOLD` | Decision threshold | 0.7 |

## Project Structure

```
.
├── api/
│   └── routes/
│       └── agent.py           # Agent endpoints
├── app/
│   └── config.py              # Configuration
├── core/
│   ├── graph/
│   │   ├── state.py           # AgentState definition
│   │   ├── nodes.py           # ReAct nodes
│   │   ├── edges.py           # Conditional edges
│   │   └── builder.py         # Graph builder
│   ├── memory/
│   │   └── mongodb_checkpointer.py  # State persistence
│   └── llm/
│       └── client.py          # LLM client
└── tools/
    ├── registry.py            # Tool registry
    ├── icd_lookup.py          # ICD-10 tool
    ├── policy_check.py        # Policy tool
    ├── coverage_calc.py       # Calculator tool
    └── document_query.py      # Document tool
```

## ReAct State

```python
{
  # Input
  "claim_id": str,
  "extracted_data": dict,
  "policy_number": str,

  # ReAct Loop
  "observations": List[str],
  "thoughts": List[str],
  "actions": List[dict],
  "reflections": List[str],

  # Context
  "retrieved_context": List[dict],
  "tool_results": List[dict],

  # Output
  "decision": "APPROVE|REJECT|PENDING",
  "confidence_score": float,
  "reasoning": str
}
```
