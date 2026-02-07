# OCR Service

FastAPI-based REST API for document OCR processing using Google Gemini AI. Part of the Insurance Claims Processing System.

**Port**: 8001

## Features

- 🔍 **Raw Text Extraction**: Extract all text from documents in natural reading order
- 📋 **Structured Field Extraction**: Extract specific fields with JSON output
- 🧠 **Thinking Mode Support**: Control model reasoning depth (Gemini 2.5 & 3.x)
- ⚙️ **Fine-grained Generation Control**: Temperature, top-p, top-k, max tokens
- 🔄 **Auto-detection**: Automatically detects Gemini 2.5 vs 3.x models
- 📁 **Multiple Input Methods**: Upload files or provide URLs
- 🛡️ **Security**: Built-in file validation, size limits, and MIME type checking

## Features

- 🔍 **Raw Text Extraction**: Extract all text from documents in natural reading order
- 📋 **Structured Field Extraction**: Extract specific fields with JSON output
- 🧠 **Thinking Mode Support**: Control model reasoning depth (Gemini 2.5 & 3.x)
- ⚙️ **Fine-grained Generation Control**: Temperature, top-p, top-k, max tokens
- 🔄 **Auto-detection**: Automatically detects Gemini 2.5 vs 3.x models
- 📁 **Multiple Input Methods**: Upload files or provide URLs
- 🛡️ **Security**: Built-in file validation, size limits, and MIME type checking

## Prerequisites

- Python 3.9+
- A Gemini API key ([Get one here](https://aistudio.google.com/apikey))

## Quick Start

### 1. Installation

```bash
# Clone and navigate to the project
cd Gemini-OCR

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file or set environment variables:

```bash
# Required
GEMINI_API_KEY=your_api_key_here

# Optional (with defaults)
GEMINI_MODEL=gemini-2.5-pro

# Generation Config (Optional)
GEMINI_TEMPERATURE=0.2
GEMINI_TOP_P=0.95
# GEMINI_TOP_K=40
# GEMINI_MAX_OUTPUT_TOKENS=8192

# Thinking Config (version-specific)
# For Gemini 2.5: -1=dynamic, 0=disabled, >0=token budget
GEMINI_THINKING_BUDGET=-1
# For Gemini 3: minimal/low/medium/high (leave commented for default "high")
# GEMINI_THINKING_LEVEL=low
```

### 3. Run the Server

```bash
# Development mode with auto-reload
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8001
```

The API will be available at `http://localhost:8001`

## API Endpoints

### Health Check
- **GET** `/health` - Check API status

### OCR Endpoints

#### Raw Text Extraction
**POST** `/api/v1/ocr/raw`

Extract all text from a document in natural reading order.

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

#### Structured Field Extraction
**POST** `/api/v1/ocr/fields`

Extract specific fields from a document with structured JSON output.

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

## Advanced Usage

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

### Using File URLs

Instead of uploading, provide a URL:
```bash
curl -X POST "http://localhost:8001/api/v1/ocr/raw" \
  -F "file_url=https://example.com/document.pdf" \
  -F "prompt=Extract text"
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

> **Note**: Gemini 3 thinking level API requires SDK update. Current implementation is prepared for future SDK support.

## File Support

- **Formats**: PNG, JPG, JPEG, PDF
- **Max Size**: 50 MB
- **Security**: Automatic MIME type validation and file sanitization

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Gemini API key (required) | - |
| `GEMINI_MODEL` | Model to use | `gemini-2.5-pro` |
| `GEMINI_TEMPERATURE` | Randomness control (0.0-2.0) | `None` |
| `GEMINI_TOP_P` | Nucleus sampling | `None` |
| `GEMINI_TOP_K` | Top-k sampling | `None` |
| `GEMINI_MAX_OUTPUT_TOKENS` | Max output tokens | `None` |
| `GEMINI_THINKING_BUDGET` | Gemini 2.5 thinking budget | `None` |
| `GEMINI_THINKING_LEVEL` | Gemini 3 thinking level | `None` |
| `PROJECT_NAME` | API name | `Gemini OCR API` |
| `VERSION` | API version | `1.0.0` |
| `API_PREFIX` | API route prefix | `/api/v1` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FILE` | Log file path | `ocr_service.log` |

## Architecture

```
Gemini-OCR/
├── src/
│   ├── app.py              # FastAPI application
│   ├── config.py           # Configuration management
│   ├── routes.py           # API endpoints
│   ├── ocr_service.py      # Gemini OCR service
│   ├── utils.py            # Utility functions
│   └── logging_config.py   # Logging setup
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
└── README.md              # This file
```

## Troubleshooting

### Common Issues

**1. SDK doesn't support `thinkingLevel` for Gemini 3**
- Current SDK version doesn't support Gemini 3's `thinkingLevel` parameter
- Code is prepared for future SDK updates
- Gemini 3 will use default "high" thinking mode until SDK is updated

**2. File too large error**
- Maximum file size is 50 MB
- Compress or split large PDFs before uploading

**3. Invalid MIME type**
- Only PNG, JPG, JPEG, and PDF files are supported
- Check file extension and actual file type

**4. API key errors**
- Verify your API key is valid at [Google AI Studio](https://aistudio.google.com/apikey)
- Ensure the key has access to the selected model

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions:
- Check the [API Documentation](http://localhost:8001/docs)
- Review logs in `ocr_service.log`
- Open an issue on GitHub
