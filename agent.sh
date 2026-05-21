#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$ROOT_DIR/src/agent-service"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

env_value() {
  local key="$1"
  local default="${2:-}"
  local value=""

  if [[ -f "$ENV_FILE" ]]; then
    value="$(awk -v key="$key" '
      /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
      {
        name = $0
        sub(/[[:space:]]*=.*/, "", name)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
        if (name == key) {
          val = $0
          sub(/^[^=]*=/, "", val)
          sub(/[[:space:]]+#.*$/, "", val)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
          gsub(/^"|"$/, "", val)
          print val
          exit
        }
      }
    ' "$ENV_FILE" 2>/dev/null || true)"
  fi

  printf '%s' "${value:-$default}"
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv first, then rerun ./agent.sh" >&2
  exit 127
fi

AGENT_HOST="${AGENT_HOST:-0.0.0.0}"
AGENT_PORT="${AGENT_PORT:-8003}"
OCR_PORT="${OCR_PORT:-8091}"
MONGO_USER="${MONGO_ROOT_USERNAME:-$(env_value MONGO_ROOT_USERNAME admin)}"
MONGO_PASS="${MONGO_ROOT_PASSWORD:-$(env_value MONGO_ROOT_PASSWORD admin123)}"
MONGO_PORT="${MONGODB_PORT:-$(env_value MONGODB_PORT 27017)}"

export HOST="$AGENT_HOST"
export PORT="$AGENT_PORT"
export OCR_SERVICE_URL="${OCR_SERVICE_URL_LOCAL:-http://localhost:${OCR_PORT}}"
export MONGODB_URL="${MONGODB_URL_LOCAL:-mongodb://${MONGO_USER}:${MONGO_PASS}@localhost:${MONGO_PORT}/claims?authSource=admin&directConnection=true}"
export UPLOADS_DIR="${UPLOADS_DIR:-$SERVICE_DIR/uploads}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:8501,http://127.0.0.1:8501}"

mkdir -p "$UPLOADS_DIR"

if [[ "${START_DEPS:-0}" == "1" ]]; then
  docker compose --project-directory "$ROOT_DIR" up -d mongodb redis
fi

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

echo "Starting Agent Service: http://localhost:${AGENT_PORT}"
echo "OCR_SERVICE_URL=$OCR_SERVICE_URL"
echo "MongoDB target: localhost:${MONGO_PORT}/claims"

exec uv run \
  --project "$ROOT_DIR" \
  --directory "$SERVICE_DIR" \
  --group agent-service \
  "${UV_ENV_ARGS[@]}" \
  uvicorn main:app \
  "${RELOAD_ARGS[@]}" \
  --host "$AGENT_HOST" \
  --port "$AGENT_PORT" \
  "$@"
