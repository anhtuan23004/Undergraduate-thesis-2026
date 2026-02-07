# Agentic AI Insurance Claims Processing System

**Khóa luận tốt nghiệp 2026** - Phát triển hệ thống đa tác tử AI cho lĩnh vực bồi thường bảo hiểm sức khỏe

## Overview

An intelligent multi-agent system for automating health insurance claims processing using:

- **OCR Service**: Document text extraction with Google Gemini
- **RAG Service**: Hybrid search (BM25 + Vector) with **Gemini embeddings**
- **Agent Service**: ReAct-based AI agent for claim decision-making with LangGraph
- **Storage**: Milvus (vector DB) + MongoDB (document & state storage)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW PIPELINE                        │
│                                                              │
│   OCR Extract → Ingest (Gemini Embed) → Hybrid Search       │
│      (8001)        (8002)                  (8002)           │
└─────────────────────────────────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌──────────┐     ┌──────────┐      ┌──────────────┐
│  OCR     │     │   RAG    │      │    Agent     │
│ Service  │     │ Service  │      │  (LangGraph) │
│ (Gemini) │     │(Hybrid   │      │  (ReAct)     │
│  :8001   │     │ Search)  │      │   :8003      │
│          │     │  :8002   │      │              │
└──────────┘     └────┬─────┘      └──────┬───────┘
                      │                    │
           ┌──────────┴──────────┐         │
           ▼                     ▼         │
    ┌──────────────┐      ┌──────────────┐ │
    │   Milvus     │      │   MongoDB    │◀┘
    │ (Vector DB)  │      │  (Memory)    │
    │   :19530     │      │   :27017     │
    └──────────────┘      └──────────────┘
```

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| OCR | 8001 | Document OCR with Gemini |
| RAG | 8002 | Hybrid search + Gemini embeddings |
| Agent | 8003 | ReAct agent with LangGraph |
| MongoDB | 27017 | Document & agent memory |
| Mongo Express | 8081 | Database UI |
| Milvus | 19530 | Vector database |
| Milvus Attu | 8000 | Vector DB UI |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- **Google Gemini API Key** (for OCR + RAG)
- **OpenAI API Key** (for Agent)

Get API keys:
- Gemini: https://makersuite.google.com/app/apikey
- OpenAI: https://platform.openai.com/api-keys

### 1. Clone & Configure

```bash
git clone <repository-url>
cd Undergraduate-thesis

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys:
# - GEMINI_API_KEY (required for OCR and RAG)
# - OPENAI_API_KEY (required for Agent)
```

### 2. Start Infrastructure

```bash
# Start MongoDB and Milvus
docker-compose up -d mongodb milvus

# Wait for services to be ready (30 seconds)
sleep 30
```

### 3. Start Application Services

```bash
# Build and start all services
docker-compose --profile app up -d --build
```

### 4. Verify Services

```bash
# Check health endpoints
curl http://localhost:8001/health  # OCR Service
curl http://localhost:8002/health  # RAG Service
curl http://localhost:8003/health  # Agent Service
```

## Usage Examples

### Complete Pipeline: OCR → Ingest → Search

```bash
# Step 1: Extract text from document using OCR
curl -X POST http://localhost:8001/api/v1/ocr/raw \
  -F "file=@insurance_policy.pdf" \
  -F "prompt=Extract all policy text"

# Step 2: Ingest extracted text into RAG (uses Gemini embeddings)
curl -X POST http://localhost:8002/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Extracted policy text here...",
    "doc_type": "insurance_policies",
    "metadata": {"source": "policy.pdf", "policy_number": "POL-001"}
  }'

# Step 3: Search for policy information
curl -X POST http://localhost:8002/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the deductible amount?", "top_k": 5}'
```

### OCR Service

```bash
# Extract raw text from document
curl -X POST http://localhost:8001/api/v1/ocr/raw \
  -F "file=@document.pdf" \
  -F "prompt=Extract patient info and diagnosis"

# Extract structured fields
curl -X POST http://localhost:8001/api/v1/ocr/fields \
  -F "file=@invoice.pdf" \
  -F "prompt=Extract invoice_number, date, total_amount as JSON"
```

### RAG Service

```bash
# Ingest document (uses Gemini embeddings - 3072 dimensions)
curl -X POST http://localhost:8002/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Policy document text...",
    "doc_type": "insurance_policies",
    "metadata": {"source": "policy_v1.pdf", "policy_number": "POL-001"}
  }'

# Hybrid search (BM25 + Vector + RRF)
curl -X POST http://localhost:8002/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "policy coverage for pneumonia",
    "top_k": 5,
    "doc_types": ["insurance_policies"]
  }'

# RAG query with context
curl -X POST http://localhost:8002/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the deductible?",
    "policy_number": "POL-001"
  }'
```

### Agent Service

```bash
# Process claim with ReAct agent
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

## Project Structure

```
.
├── src/
│   ├── ocr-service/          # OCR with Gemini (port 8001)
│   ├── rag-service/          # RAG with Gemini embeddings (port 8002)
│   └── agent-service/        # Agent with LangGraph (port 8003)
├── infrastructure/
│   ├── mongodb/              # MongoDB config
│   └── milvus/               # Milvus config
├── docker-compose.yml        # Main compose file
├── .env.example              # Environment template
└── README.md                 # This file
```

## Environment Variables

Create `.env` file from `.env.example`:

```bash
# Required API Keys
GEMINI_API_KEY=your_gemini_key_here      # For OCR + RAG
OPENAI_API_KEY=sk-your_openai_key_here   # For Agent

# Database (auto-configured in Docker)
MONGODB_URL=mongodb://claims_app:claims_password@localhost:27017/claims
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Service URLs
OCR_SERVICE_URL=http://localhost:8001
RAG_SERVICE_URL=http://localhost:8002
AGENT_SERVICE_URL=http://localhost:8003
```

**Important**: RAG service now uses **Gemini embeddings** (3072 dimensions), not OpenAI embeddings.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11 |
| Web Framework | FastAPI 0.109.0 |
| OCR | Google Gemini API |
| Embeddings | Google Gemini (`gemini-embedding-001`, 3072 dims) |
| Agent Framework | LangGraph 0.0.50 |
| Vector DB | Milvus 2.5.6 |
| Document DB | MongoDB 7.0.4 |
| Server | Uvicorn 0.27.0 |

## Documentation

- [CLAUDE.md](CLAUDE.md) - Development guide for Claude Code
- [OCR Service](src/ocr-service/README.md) - Document processing
- [RAG Service](src/rag-service/README.md) - Hybrid search with Gemini embeddings
- [Agent Service](src/agent-service/README.md) - ReAct agent
- [MongoDB](infrastructure/mongodb/README.md) - Database setup
- [Milvus](infrastructure/milvus/README.md) - Vector database

## Development

```bash
# Run services individually for development

# OCR Service
cd src/ocr-service
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8001

# RAG Service
cd src/rag-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002

# Agent Service
cd src/agent-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003
```

## License

MIT License - See [LICENSE](LICENSE) file

## Author

**Tuan Mai** - Undergraduate Thesis 2026

---

*Built with FastAPI, LangGraph, Milvus, MongoDB, and Google Gemini*
