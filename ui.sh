#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/src/agent-service/interfaces/web"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv first, then rerun ./ui.sh" >&2
  exit 127
fi

UI_HOST="${UI_HOST:-0.0.0.0}"
UI_PORT="${UI_PORT:-8501}"

UV_ENV_ARGS=()
if [[ -f "$ENV_FILE" ]]; then
  UV_ENV_ARGS=(--env-file "$ENV_FILE")
fi

export STREAMLIT_BROWSER_GATHER_USAGE_STATS="${STREAMLIT_BROWSER_GATHER_USAGE_STATS:-false}"

echo "Starting Streamlit UI: http://localhost:${UI_PORT}"
echo "Default Agent API URL in UI: http://localhost:8003"

exec uv run \
  --project "$ROOT_DIR" \
  --directory "$WEB_DIR" \
  --group agent-service \
  "${UV_ENV_ARGS[@]}" \
  streamlit run app.py \
  --server.address "$UI_HOST" \
  --server.port "$UI_PORT" \
  "$@"
