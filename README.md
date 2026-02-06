# Agentic AI Insurance Claims Processing System

**Khóa luận tốt nghiệp 2026** - Phát triển hệ thống đa tác tử AI cho lĩnh vực bồi thường bảo hiểm sức khỏe

## Overview

An intelligent system for automating health insurance claims processing using:
- **OCR**: Document text extraction with Google Gemini
- **RAG**: Hybrid search (BM25 + Vector) for policy retrieval
- **Agent**: ReAct-based AI agent for claim decision-making
- **Workflow**: Dify orchestration for end-to-end processing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DIFY WORKFLOW                            │
│         (Visual Workflow Orchestration)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌──────────┐     ┌──────────┐      ┌──────────────┐
│  OCR     │     │   RAG    │      │    Agent     │
│ Service  │     │ Service  │      │  (LangGraph) │
│ (Gemini) │     │(Hybrid   │      │  (ReAct)     │
│          │     │ Search)  │      │              │
└──────────┘     └────┬─────┘      └──────┬───────┘
                      │                    │
           ┌──────────┴──────────┐         │
           ▼                     ▼         │
    ┌──────────────┐      ┌──────────────┐ │
    │   Milvus     │      │   MongoDB    │◀┘
    │ (Vector DB)  │      │  (Memory)    │
    └──────────────┘      └──────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API Key
- Google Gemini API Key

### 1. Clone & Configure

```bash
git clone <repository-url>
cd Undergraduate-thesis

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys
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

### 5. Access Web UIs

| Service | URL | Description |
|---------|-----|-------------|
| Mongo Express | http://localhost:8081 | Database management |
| Milvus Attu | http://localhost:8000 | Vector database UI |
| MinIO Console | http://localhost:9001 | Object storage |

## Services

| Service | Port | Description | Documentation |
|---------|------|-------------|---------------|
| OCR | 8001 | Document OCR with Gemini | [README](src/ocr-service/README.md) |
| RAG | 8002 | Hybrid search + embeddings | [README](src/rag-service/README.md) |
| Agent | 8003 | ReAct agent with LangGraph | [README](src/agent-service/README.md) |
| MongoDB | 27017 | Document & agent memory | [README](infrastructure/mongodb/README.md) |
| Milvus | 19530 | Vector database | [README](infrastructure/milvus/README.md) |

## API Usage Examples

### OCR Service

```bash
# Extract text from document
curl -X POST http://localhost:8001/api/v1/ocr/raw \
  -F "file=@invoice.pdf" \
  -F "prompt=Extract patient info and diagnosis"
```

### RAG Service

```bash
# Hybrid search
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
    "query": "What is the deductible amount?",
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
│   ├── ocr-service/          # OCR with Gemini
│   ├── rag-service/          # RAG with hybrid search
│   └── agent-service/        # Agent with LangGraph
├── infrastructure/
│   ├── mongodb/              # MongoDB config
│   ├── milvus/               # Milvus config
│   └── dify/                 # Dify workflow engine
├── docker-compose.yml        # Main compose file
├── .env.example              # Environment template
├── des-hybrid.md             # Detailed PRD
└── README.md                 # This file
```

## Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| OCR Accuracy | >85% | 🚧 In Progress |
| RAG Search Latency | <100ms | ✅ Ready |
| Agent Decision Time | <30s | ✅ Ready |
| Extraction Accuracy | >90% | 🚧 In Progress |

## Development

```bash
# Run services individually
cd src/ocr-service
pip install -r requirements.txt
python -m uvicorn api.main:app --reload

# Run tests
cd src/agent-service
pytest tests/

# Check logs
docker-compose logs -f agent-service
```

## Documentation

- [Detailed PRD](des-hybrid.md) - Product requirements with 120+ tasks
- [OCR Service](src/ocr-service/README.md) - Document processing
- [RAG Service](src/rag-service/README.md) - Hybrid search
- [Agent Service](src/agent-service/README.md) - ReAct agent
- [MongoDB](infrastructure/mongodb/README.md) - Database setup
- [Milvus](infrastructure/milvus/README.md) - Vector database

## License

MIT License - See [LICENSE](LICENSE) file

## Author

**Tuan Mai** - Undergraduate Thesis 2026

---

*Built with FastAPI, LangGraph, Milvus, MongoDB, and Gemini*
