# OCR Service

Document OCR microservice powered by **Google Gemini Vision**. Provides two API versions: a simple text/field extraction pipeline (V1) and a schema‑driven, multi‑document classification + extraction pipeline (V2).

---

## Table of Contents

- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Run Locally](#run-locally)
- [Docker](#docker)
- [Project Structure](#project-structure)
- [API Examples](#api-examples)

---

## Architecture

The service is layered into four tiers:

```
API Layer           →  api/routes.py, api/utils.py
Schemas             →  schemas.py
Core Engine         →  core/engine/base.py (BaseGeminiEngine, DocumentDetector)
                       core/engine/v1.py   (GeminiOCREngine — raw/fields)
                       core/engine/v2.py   (OCRServiceV2 — classify + extract)
                       core/prompts.py     (PromptBuilder)
Utilities           →  utils/gemini.py, utils/pdf.py, utils/schema_builder.py
```

### V2 Pipeline Flow

```
┌───────────────┐          ┌─────────────────────┐         ┌─────────────────────┐
│  Prefilter    │──pass──▶ │ Phase 1: Classify   │──docs──▶│ Phase 2: Extract    │
│  (optional)   │          │ & Segment           │         │ (parallel per doc)  │
└───────────────┘          └─────────────────────┘         └─────────────────────┘
 Samples 3 pages            JSON Schema output              Sliced PDF per segment
 to reject junk             document boundaries             ThreadPoolExecutor(3)
```

---

## API Endpoints

### V1 — Simple Extraction

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ocr/raw` | Extract free‑form text (multipart form) |
| `POST` | `/api/v1/ocr/fields` | Extract structured fields (multipart form) |

### V2 — Schema‑Driven Pipeline (JSON body)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/ocr/prefilter` | Quick validity check before heavy processing |
| `POST` | `/api/v2/ocr/classify-segment` | Phase 1 only — classify and locate document boundaries |
| `POST` | `/api/v2/ocr/extract` | Full 2‑stage pipeline (classify → slice → extract) |

### V2 — Schema‑Driven Pipeline (multipart/form)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/ocr/classify-segment/form` | Phase 1 with file upload support |
| `POST` | `/api/v2/ocr/extract/form` | Full pipeline with file upload support |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service liveness probe |

---

## Configuration

All settings are managed via environment variables (`.env`) and loaded through Pydantic Settings.

```bash
# ── Required ────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key

# ── Model Defaults ──────────────────────────────────────
GEMINI_MODEL=gemini-2.5-pro        # Default model for all calls
GEMINI_TEMPERATURE=                 # 0.0–2.0 (None = model default)
GEMINI_TOP_P=                       # Nucleus sampling
GEMINI_TOP_K=                       # Top-k sampling
GEMINI_MAX_OUTPUT_TOKENS=           # Max output length

# ── Thinking Configuration ──────────────────────────────
GEMINI_THINKING_BUDGET=             # Gemini 2.5: -1=dynamic, 0=off, >0=budget
GEMINI_THINKING_LEVEL=              # Gemini 3: minimal/low/medium/high

# ── V2 Pipeline ─────────────────────────────────────────
GEMINI_MAX_INLINE_IN_BYTES=104857600   # 100 MB — above this, use Files API
GEMINI_MAX_CONCURRENT_EXTRACTIONS=3    # Phase 2 thread pool workers

# ── Application ─────────────────────────────────────────
PROJECT_NAME="Gemini OCR API"
VERSION="1.0.0"
API_PREFIX="/api/v1"
LOG_LEVEL=INFO
LOG_FILE=ocr_service.log
```

All V2 endpoints also accept per‑request overrides for `model_name`, `temperature`, `top_p`, `top_k`, `max_output_tokens`, `thinking_budget`, and `thinking_level`.

---

## Run Locally

### With `uv` (recommended)

```bash
cd src/ocr-service
PYTHONPATH=. uv run uvicorn main:app --reload --port 8001
```

### With `pip`

```bash
cd src/ocr-service
pip install -r requirements.txt
PYTHONPATH=. uvicorn main:app --reload --port 8001
```

Then open <http://localhost:8001/docs> for the interactive Swagger UI.

---

## Docker

The service is included in the root `docker-compose.yml`:

- **Container port**: `8000`
- **Host port**: `8001`

```bash
# Build and start the OCR service only
docker-compose up -d --build ocr-service

# Verify
curl http://localhost:8001/health
```

---

## Project Structure

```
src/ocr-service/
├── main.py                  # FastAPI application entry point
├── requirements.txt         # pip dependencies
├── Dockerfile               # Container build
├── .env.example             # Environment template
│
├── api/                     # Route handlers
│   ├── health.py            # GET /health
│   ├── v1.py                # V1 raw/fields endpoints
│   ├── v2.py                # V2 JSON + form endpoints
│   └── utils.py             # Shared helpers (file input, error handler)
│
├── schemas/                 # Pydantic request/response models
│   ├── v1.py                # V1 schemas
│   └── v2.py                # V2 schemas (ExtractionSchema, ClassificationSchema, etc.)
│
├── core/                    # Business logic
│   ├── config.py            # Settings (Pydantic BaseSettings)
│   ├── prompts.py           # PromptBuilder for Phase 1 & Phase 2
│   └── engine/
│       ├── base.py          # BaseGeminiEngine, DocumentDetector, GeminiConfigError
│       ├── v1.py            # GeminiOCREngine (simple extraction)
│       └── v2.py            # OCRServiceV2 (classify → segment → extract)
│
└── utils/                   # Shared utilities
    ├── gemini.py            # Gemini API helpers, download_file_from_url
    ├── pdf.py               # PDF slicing (PyMuPDF)
    ├── schema_builder.py    # JSON Schema builders for structured output
    └── logging.py           # Logging setup
```

---

## API Examples

### V1 — Extract raw text

```bash
curl -X POST "http://localhost:8001/api/v1/ocr/raw" \
  -F "file=@document.pdf" \
  -F "prompt=Extract patient information and diagnosis"
```

### V2 — Classify and segment (JSON)

```bash
curl -X POST "http://localhost:8001/api/v2/ocr/classify-segment" \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://example.com/claim.pdf",
    "extraction_schemas": [
      {
        "document_code": "medical_certificate",
        "document_name": "Giấy chứng nhận nghỉ việc hưởng BHXH"
      }
    ]
  }'
```

### V2 — Full extraction (multipart/form)

```bash
curl -X POST "http://localhost:8001/api/v2/ocr/extract/form" \
  -F "file=@bundle.pdf" \
  -F 'extraction_schemas=[{"document_code":"claim_form","document_name":"Đơn yêu cầu bồi thường","fields":[{"field_name":"patient_name","field_type":"string"}]}]'
```
