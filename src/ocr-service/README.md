# OCR Service

FastAPI-based REST API for document OCR processing using Google Gemini AI. Part of the Insurance Claims Processing System.

## Overview

The OCR Service provides document text extraction capabilities using Google's Gemini AI models. It supports both raw text extraction and structured field extraction from various document formats including PDFs and images.

This service is the entry point for document processing in the claims workflow, extracting text that can then be ingested into the RAG service for policy search and analysis.

## Features

- Raw text extraction from documents in natural reading order
- Structured field extraction with JSON output
- Thinking mode support for controlling model reasoning depth (Gemini 2.5 & 3.x)
- Fine-grained generation control (temperature, top-p, top-k, max tokens)
- Auto-detection of Gemini 2.5 vs 3.x models
- Multiple input methods (file upload or URL)
- Security with file validation, size limits, and MIME type checking

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   FastAPI   │────▶│   Gemini    │
│  (Upload)   │     │   Server    │     │    API      │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │   Logging   │
                     │  (ocr.log)  │
                     └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- Gemini API key (get from https://aistudio.google.com/apikey)

### Setup

```bash
# Navigate to service directory
cd src/ocr-service

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
# Required
GEMINI_API_KEY=your_api_key_here

# Optional (with defaults)
GEMINI_MODEL=gemini-2.5-pro
GEMINI_TEMPERATURE=0.2
GEMINI_TOP_P=0.95
GEMINI_THINKING_BUDGET=-1
```

### Run the Server

```bash
# Development mode with auto-reload
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

The API will be available at `http://localhost:8001`

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Gemini API key (required) | - |
| `GEMINI_MODEL` | Model to use | `gemini-2.5-pro` |
| `GEMINI_TEMPERATURE` | Randomness control (0.0-2.0) | None |
| `GEMINI_TOP_P` | Nucleus sampling | None |
| `GEMINI_TOP_K` | Top-k sampling | None |
| `GEMINI_MAX_OUTPUT_TOKENS` | Max output tokens | None |
| `GEMINI_THINKING_BUDGET` | Gemini 2.5 thinking budget | None |
| `GEMINI_THINKING_LEVEL` | Gemini 3 thinking level | None |
| `PROJECT_NAME` | API name | `Gemini OCR API` |
| `VERSION` | API version | `1.0.0` |
| `API_PREFIX` | API route prefix | `/api/v1` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FILE` | Log file path | `ocr_service.log` |

## Usage

### Health Check

```bash
curl http://localhost:8001/health
```

### Raw Text Extraction

Extract all text from a document in natural reading order.

**Endpoint:** `POST /api/v1/ocr/raw`

**Parameters:**
- `file` (file, optional): Upload file directly
- `file_url` (string, optional): URL to download file from
- `prompt` (string, optional): Custom extraction instructions
- `model_name` (string, optional): Override default model
- `temperature` (float, optional): Controls randomness (0.0-2.0)
- `top_p` (float, optional): Nucleus sampling threshold
- `top_k` (int, optional): Top-k sampling parameter
- `max_output_tokens` (int, optional): Maximum tokens to generate
- `thinking_budget` (int, optional): Token budget for Gemini 2.5 (-1=dynamic, 0=disabled, >0=budget)
- `thinking_level` (string, optional): Thinking level for Gemini 3 (minimal/low/medium/high)

**Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/ocr/raw" \
  -F "file=@document.pdf" \
  -F "prompt=Extract all text preserving layout" \
  -F "temperature=0.2"
```

### Structured Field Extraction

Extract specific fields from a document with structured JSON output.

**Endpoint:** `POST /api/v1/ocr/fields`

**Parameters:** Same as `/ocr/raw`

**Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/ocr/fields" \
  -F "file=@invoice.jpg" \
  -F "prompt=Extract invoice_number, date, total_amount, vendor_name as JSON" \
  -F "thinking_level=high"
```

**Response:**
```json
{
  "invoice_number": "INV-2024-001",
  "date": "2024-01-15",
  "total_amount": "$1,234.56",
  "vendor_name": "ACME Corp"
}
```

### Using File URLs

Instead of uploading, provide a URL:
```bash
curl -X POST "http://localhost:8001/api/v1/ocr/raw" \
  -F "file_url=https://example.com/document.pdf" \
  -F "prompt=Extract text"
```

## Development

### Project Structure

```
src/ocr-service/
├── api/
│   ├── main.py              # FastAPI application entry
│   ├── routes.py            # API endpoints
│   └── dependencies.py      # FastAPI dependencies
├── core/
│   ├── ocr_engine.py        # Gemini OCR implementation
│   └── file_handler.py      # File upload handling
├── app/
│   └── config.py            # Configuration management
├── utils/
│   └── logging_config.py    # Logging setup
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

### Thinking Mode

#### Gemini 2.5 Series

Control reasoning depth with token budget:
```bash
# Dynamic thinking (recommended)
-F "thinking_budget=-1"

# Disable thinking (faster, less accurate)
-F "thinking_budget=0"

# Custom budget (e.g., 1024 tokens)
-F "thinking_budget=1024"
```

#### Gemini 3 Series

Control reasoning level:
```bash
# Minimal thinking (fastest, Gemini 3 Flash only)
-F "thinking_level=minimal"

# Low thinking (balanced)
-F "thinking_level=low"

# Medium thinking
-F "thinking_level=medium"

# High thinking (most accurate, default)
-F "thinking_level=high"
```

### Generation Parameters

Fine-tune model behavior:
```bash
curl -X POST "http://localhost:8001/api/v1/ocr/fields" \
  -F "file=@document.pdf" \
  -F "prompt=Extract key fields" \
  -F "temperature=0.7" \
  -F "top_p=0.95" \
  -F "top_k=40" \
  -F "max_output_tokens=2048"
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8001/docs`
- **ReDoc**: `http://localhost:8001/redoc`

## Supported Models

### Gemini 2.5 Series
- `gemini-2.5-pro` (default)
- `gemini-2.5-flash`

### Gemini 3 Series
- `gemini-3-flash-preview`
- `gemini-3-pro` (when available)

## File Support

- **Formats**: PNG, JPG, JPEG, PDF
- **Max Size**: 50 MB
- **Security**: Automatic MIME type validation and file sanitization

## Troubleshooting

### SDK doesn't support `thinkingLevel` for Gemini 3
- Current SDK version doesn't support Gemini 3's `thinkingLevel` parameter
- Code is prepared for future SDK updates
- Gemini 3 will use default "high" thinking mode until SDK is updated

### File too large error
- Maximum file size is 50 MB
- Compress or split large PDFs before uploading

### Invalid MIME type
- Only PNG, JPG, JPEG, and PDF files are supported
- Check file extension and actual file type

### API key errors
- Verify your API key is valid at [Google AI Studio](https://aistudio.google.com/apikey)
- Ensure the key has access to the selected model

## License

MIT License - See LICENSE file for details
