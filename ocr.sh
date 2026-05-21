#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$ROOT_DIR/src/ocr-service"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv first, then rerun ./ocr.sh" >&2
  exit 127
fi

OCR_HOST="${OCR_HOST:-0.0.0.0}"
OCR_PORT="${OCR_PORT:-8091}"

UV_ENV_ARGS=()
if [[ -f "$ENV_FILE" ]]; then
  UV_ENV_ARGS=(--env-file "$ENV_FILE")
else
  echo "Warning: $ENV_FILE not found. Create it from .env.example if GEMINI_API_KEY is missing." >&2
fi

RELOAD_ARGS=()
case "${RELOAD:-1}" in
  0|false|False|FALSE|no|No|NO) ;;
  *) RELOAD_ARGS=(--reload --reload-dir "$SERVICE_DIR") ;;
esac

echo "Starting OCR Service: http://localhost:${OCR_PORT}"

exec uv run \
  --project "$ROOT_DIR" \
  --directory "$SERVICE_DIR" \
  --group ocr-service \
  "${UV_ENV_ARGS[@]}" \
  uvicorn main:app \
  "${RELOAD_ARGS[@]}" \
  --host "$OCR_HOST" \
  --port "$OCR_PORT" \
  "$@"
