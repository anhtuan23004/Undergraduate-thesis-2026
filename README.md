# Agentic AI Insurance Claims Processing System

A multi-service system for automated health insurance claim processing using LangGraph multi-agent architecture.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Documentation](#api-documentation)
- [Local Development](#local-development)
- [Web UI](#web-ui)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Overview

This system automates insurance claim processing through three specialized AI agents:

| Agent | Role |
|-------|------|
| **Completeness Agent** | Verifies document completeness and required fields |
| **Quality Agent** | Validates medical quality (ICD codes, medications, exclusions) |
| **Decision Agent** | Makes final claim approval/rejection decisions |

The system includes a **human-in-the-loop** workflow that pauses for human review when needed.

## Features

- Multi-agent workflow using LangGraph
- Document OCR processing via Google Gemini Vision
- Hybrid search (BM25 + Vector) for medical knowledge
- Human review interface with workflow resumption
- SSE streaming for real-time status updates
- MongoDB persistence for workflow state
- Web UI for claim management

## Prerequisites

### Required

- **Docker** (version 20.10+) - [Install Guide](https://docs.docker.com/get-docker/)
- **Docker Compose** (version 2.0+) - Usually included with Docker Desktop

### API Keys

| Service | Required? | How to Get |
|----------|------------|------------|
| Google Gemini API | **Yes** | [Google AI Studio](https://makersuite.google.com/app/apikey) |
| OpenAI API | Optional | [OpenAI Platform](https://platform.openai.com/api-keys) |
| HuggingFace Token | Optional | [Hugging Face Settings](https://huggingface.co/settings/tokens) |

## Quick Start

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Undergraduate-thesis
```

### Step 2: Set Up Environment Variables

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and set your `GEMINI_API_KEY`:

```bash
# Required
GEMINI_API_KEY=your_actual_gemini_api_key_here

# Optional - for additional features
OPENAI_API_KEY=
HF_TOKEN=
```

### Step 3: Start All Services

```bash
docker-compose up -d --build
```

This will:

- Build the OCR and Agent service Docker images
- Start MongoDB and Mongo Express (from `infrastructure/mongodb/`)
- Start Langfuse services (optional, from `infrastructure/langfuse/`)
- Start OCR service on port `8001`
- Start Agent service on port `8003`

**Total services: 10** (2 app services + 8 infrastructure services)

### Step 4: Verify Services Are Running

Check that all services are healthy:

```bash
docker-compose ps
```

You should see all services marked as `Up` or `healthy`.

Test the health endpoints:

```bash
# OCR Service
curl http://localhost:8001/health

# Agent Service
curl http://localhost:8003/health
```

### Step 5: Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| Agent API | <http://localhost:8003/docs> | API Documentation (Swagger) |
| Agent Health | <http://localhost:8003/health> | Service Health Check |
| OCR Health | <http://localhost:8001/health> | OCR Service Health Check |
| Mongo Express | <http://localhost:8081> | MongoDB Web UI |
| Langfuse Web | <http://localhost:3000> | Observability Dashboard (optional) |

### Step 6: Run the Web UI (Optional)

```bash
cd src/agent-service
streamlit run interfaces/web/app.py
```

Then open <http://localhost:8501> in your browser.

## Architecture

### System Components

```
┌─────────────────┐
│   User / Claim  │
│   Submission    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   OCR Service   │ ◄── Gemini Vision API
│  (Text Extract) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│          Agent Service                │
│  ┌─────────────────────────────────┐  │
│  │      LangGraph Workflow        │  │
│  │                               │  │
│  │  Completeness ──► Quality     │  │
│  │       │            │           │  │
│  │       └────┬───────┘           │  │
│  │            ▼                   │  │
│  │        Decision                │  │
│  └─────────────────────────────────┘  │
└────────┬──────────────────────────────┘
         │
         ▼
┌─────────────────┐
│     MongoDB     │
│  (State Store)  │
└─────────────────┘
```

### Multi-Agent Workflow

```
completeness_check → (route) → quality_check → (route) → final_decision
        ↓                    ↓                ↓
  agent_review        agent_review       human_review (interrupt)
        ↓                    ↓
        human_review        human_review
```

## API Documentation

### Agent Service Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/workflows/run` | Start new claim workflow |
| POST | `/api/v1/workflows/run-stream` | Start with SSE streaming |
| POST | `/api/v1/workflows/resume/{run_id}` | Resume after human review |
| POST | `/api/v1/workflows/continue/{run_id}` | Continue after pause |
| GET | `/api/v1/workflows/status/{run_id}` | Get workflow status |
| GET | `/api/v1/workflows/stream/{run_id}` | Stream existing workflow |

### OCR Service Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ocr/raw` | Extract raw text from document |
| POST | `/api/v1/ocr/fields` | Extract specific fields from document |

### Interactive API Docs

Visit <http://localhost:8003/docs> to see the full interactive API documentation powered by Swagger UI.

## Local Development

### Installing Dependencies with `uv`

The project uses `uv` dependency groups defined in `pyproject.toml`. After cloning, you can install dependencies with:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv | sh

# Install ALL dependencies
uv sync

# Install only specific service dependencies
uv sync --group agent-service
uv sync --group ocr-service

# Install with dev dependencies (includes testing tools)
uv sync --all-extras
```

**Dependency Groups Available:**

| Group | Description |
|--------|-------------|
| `agent-service` | LangGraph, MongoDB, LangChain dependencies |
| `ocr-service` | Google Gemini API, FastAPI dependencies |
| `rag-service` | RAG/Hybrid search dependencies |
| `dev` | Testing, linting, type checking tools |

### Running Services Locally (Without Docker)

After installing dependencies, run services directly:

```bash
# OCR Service
cd src/ocr-service
uv run uvicorn api.main:app --reload --port 8001

# Agent Service
cd src/agent-service
uv run uvicorn main:app --reload --port 8003

# Streamlit Web UI
cd src/agent-service
uv run streamlit run interfaces/web/app.py
```

### Starting Specific Infrastructure Services

If you only need certain infrastructure services (not all), you can run them from their subdirectories:

```bash
# Start only MongoDB and Mongo Express
cd infrastructure/mongodb
docker-compose -f docker-compose-mongodb.yml up -d

# Start only Langfuse services
cd infrastructure/langfuse
docker-compose -f docker-compose.langfuse.yml up -d
```

### Running Services Without Docker

For development, you can run services directly with Python:

#### 1. Start Infrastructure Only

```bash
# Start just MongoDB
docker-compose up -d mongodb mongo-express
```

#### 2. Run OCR Service

```bash
cd src/ocr-service
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8001
```

#### 3. Run Agent Service

```bash
cd src/agent-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

## Project Structure

```
Undergraduate-thesis/
├── docker-compose.yml           # Main orchestration file
├── .env.example                # Environment variables template
├── README.md                   # This file
│
├── src/
│   ├── ocr-service/            # Document OCR processing
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── api/
│   │       └── main.py
│   │
│   └── agent-service/          # Multi-agent workflow
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── main.py             # FastAPI app entry
│       ├── graphs/             # LangGraph workflow
│       ├── agents/             # Agent implementations
│       ├── skills/             # Agent skills
│       └── interfaces/        # Web UI
│
├── infrastructure/              # Supporting services
│   ├── mongodb/
│   └── langfuse/
│
└── docs/                      # Documentation
```

## Testing

### Running Tests

The project includes unit tests for all services. Install dev dependencies first:

```bash
# Install with testing tools
uv sync --all-extras

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run tests for specific service
uv run pytest src/agent-service/tests/
uv run pytest src/ocr-service/tests/
```

## Web UI

The system includes a Streamlit web interface for claim management and workflow monitoring.

### Starting the Web UI

```bash
# After installing dependencies
cd src/agent-service
uv run streamlit run interfaces/web/app.py
```

Then open <http://localhost:8501> in your browser.

### Web UI Features

| Feature | Description |
|---------|-------------|
| **Claim Input** | Submit new claims with file upload |
| **Workflow Status** | Real-time view of workflow progress |
| **Human Review Panel** | Interface for reviewing interrupted claims |
| **History** | View previous claim submissions |
| **Session Management** | Track multiple workflow sessions |

### Workflow States

| State | Description | Action Required |
|--------|-------------|-----------------|
| `pending` | Workflow waiting to start | None |
| `completeness_check` | Completeness agent running | Wait for completion |
| `quality_check` | Quality agent running | Wait for completion |
| `agent_review` | Automated review in progress | Wait for completion |
| `human_review` | Paused for human review | **Submit review decision** |
| `final_decision` | Final decision made | None |
| `completed` | Workflow finished | None |

## Troubleshooting

### Services Not Starting

1. Check if ports are already in use:

   ```bash
   lsof -i :8001
   lsof -i :8003
   lsof -i :27017
   ```

2. Check service logs:

   ```bash
   docker-compose logs -f [service-name]
   ```

### API Key Errors

- Verify your `GEMINI_API_KEY` is correctly set in `.env`
- Ensure the API key has the necessary permissions
- Check if you've reached your API quota

### MongoDB Connection Issues

- Verify MongoDB is healthy:

  ```bash
  docker-compose ps mongodb
  ```

- Check MongoDB logs:

  ```bash
  docker-compose logs -f mongodb
  ```

### Rebuild Services

If you make changes to the code:

```bash
# Rebuild and restart
docker-compose up -d --build

# Or rebuild specific service
docker-compose up -d --build agent-service
```

### Clean Up

Stop all services and remove containers:

```bash
docker-compose down
```

Stop and remove containers, volumes, and networks:

```bash
docker-compose down -v
```

## Additional Resources

- [OCR Service README](src/ocr-service/README.md)
- [Agent Service README](src/agent-service/README.md)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API Docs](https://ai.google.dev/docs)

## License

MIT
