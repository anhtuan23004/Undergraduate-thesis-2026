# OCR Service

Document OCR API using Google Gemini models.

## Runtime Summary

- Framework: FastAPI (`uvicorn api.main:app`)
- Default port: `8000` (host mapped to `8001` in Docker Compose)
- Input: PDF/JPG/JPEG/PNG
- Output:
  - raw text extraction
  - structured fields extraction

## API Endpoints

Routes use `API_PREFIX` (default `/api/v1`).

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/ocr/raw` | Extract free-form text |
| `POST` | `/api/v1/ocr/fields` | Extract structured fields |
| `GET` | `/health` | Service health |

## Configuration

```bash
PROJECT_NAME="OCR Service"
VERSION="1.0.0"
API_PREFIX="/api/v1"

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-pro

LOG_LEVEL=INFO
LOG_FILE=ocr_service.log
```

Optional generation parameters are supported by request form fields:
- `temperature`
- `top_p`
- `top_k`
- `max_output_tokens`
- `thinking_budget` (Gemini 2.5)
- `thinking_level` (Gemini 3)

See [`src/ocr-service/.env.example`](./.env.example) for base template.

## Run Locally

```bash
cd src/ocr-service
pip install -r requirements.txt
uvicorn api.main:app --reload --host 0.0.0.0 --port 8001
```

## Docker Runtime

In root compose (`docker-compose.yml`):
- container port `8000`
- host port `8001`

```bash
docker-compose up -d --build ocr-service
curl http://localhost:8001/health
```

## Quick API Example

```bash
curl -X POST "http://localhost:8001/api/v1/ocr/raw" \
  -F "file=@document.pdf" \
  -F "prompt=Extract patient information and diagnosis"
```
