# Agent Service

ReAct-based AI agent for insurance claim decision-making using LangGraph and OpenAI.

## Overview

The Agent Service implements a ReAct (Reasoning + Acting) AI agent that processes insurance claims and makes approval decisions. It uses the LangGraph framework to orchestrate a loop of observation, thinking, action, and reflection to arrive at well-reasoned claim decisions.

This service is the decision-making core of the claims processing system, leveraging the RAG service for policy context and persisting state to MongoDB for reliability.

## Features

- ReAct (Reasoning + Acting) loop architecture
- Extensible tool system for claim validation
- MongoDB checkpointing for state persistence
- Structured JSON output for decisions
- LangGraph-based agent framework
- Confidence scoring for decisions

## Architecture

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Observe │───▶│  Think  │───▶│   Act   │───▶│ Reflect │───▶│ Decide  │
│         │    │         │    │ (Tool)  │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘    └─────────┘
       ▲                                           │
       │                                           │
       └───────────────────────────────────────────┘
                    (loop if needed)
```

### State Flow

```
Input (claim_id, extracted_data, policy_number)
    ↓
Observe → Gather context from RAG service
    ↓
Think → Analyze and plan next action
    ↓
Act → Execute tool (icd_lookup, policy_check, etc.)
    ↓
Reflect → Evaluate results and decide to continue or decide
    ↓
Output (decision, confidence_score, reasoning)
```

## Quick Start

### Prerequisites

- MongoDB running (port 27017)
- RAG Service running (port 8002)
- OpenAI API Key

### Setup

```bash
cd src/agent-service
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_key_here
MONGODB_URL=mongodb://claims_app:claims_password@localhost:27017/claims
RAG_SERVICE_URL=http://localhost:8002
```

### Run Service

```bash
uvicorn app.main:app --reload --port 8003
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | Model name | `gpt-4` |
| `MONGODB_URL` | MongoDB connection string | Required |
| `RAG_SERVICE_URL` | RAG service endpoint | `http://localhost:8002` |
| `MAX_ITERATIONS` | Max ReAct iterations | `10` |
| `CONFIDENCE_THRESHOLD` | Decision threshold | `0.7` |

## Usage

### Health Check

```bash
curl http://localhost:8003/health
```

### Process Claim

**Endpoint:** `POST /api/v1/agent/decide`

Process a claim and return a decision with reasoning.

**Example:**
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

**Response:**
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

### Get Graph Structure

**Endpoint:** `GET /api/v1/agent/graph`

Returns the LangGraph structure for visualization.

## Development

### Project Structure

```
src/agent-service/
├── api/
│   └── routes/
│       └── agent.py           # Agent endpoints
├── app/
│   └── config.py              # Configuration
├── core/
│   ├── graph/
│   │   ├── state.py           # AgentState definition
│   │   ├── nodes.py           # ReAct nodes (observe, think, act, reflect)
│   │   ├── edges.py           # Conditional edges
│   │   └── builder.py         # Graph builder
│   ├── memory/
│   │   └── mongodb_checkpointer.py  # State persistence
│   └── llm/
│       └── client.py          # LLM client
├── tools/
│   ├── registry.py            # Tool registry
│   ├── icd_lookup.py          # ICD-10 tool
│   ├── policy_check.py        # Policy tool
│   ├── coverage_calc.py       # Calculator tool
│   └── document_query.py      # Document tool
├── requirements.txt           # Python dependencies
└── README.md                 # This file
```

### Available Tools

| Tool | Description |
|------|-------------|
| `icd_lookup` | Validate ICD-10 diagnosis codes |
| `policy_check` | Check policy terms and coverage |
| `coverage_calc` | Calculate eligible claim amounts |
| `document_query` | Query extracted document fields |

### ReAct State

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

## Troubleshooting

### MongoDB connection errors

- Verify MongoDB is running on port 27017
- Check `MONGODB_URL` in `.env` file
- Ensure credentials are correct

### RAG service unavailable

- Verify RAG service is running on port 8002
- Check `RAG_SERVICE_URL` in `.env` file
- Review RAG service logs

### OpenAI API errors

- Verify `OPENAI_API_KEY` is set correctly
- Check that the API key has not expired
- Review rate limits on your OpenAI account

### Decision timeout

- Increase `MAX_ITERATIONS` if complex claims need more processing
- Check that all tools are responding correctly
- Review logs for specific error messages

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8003/docs`
- **ReDoc**: `http://localhost:8003/redoc`
