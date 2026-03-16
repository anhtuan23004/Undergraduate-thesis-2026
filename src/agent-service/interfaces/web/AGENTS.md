<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-26 | Updated: 2026-03-16 -->

# web/

## Purpose

Streamlit-based UI for claim submission, workflow monitoring, human review, and result visualization. This layer only orchestrates UI state and HTTP calls to `interfaces/api` endpoints.

## Key Files

| File | Description |
|------|-------------|
| `app.py` | App entrypoint and top-level screen flow (`main`) |
| `api_client.py` | HTTP helpers for multi-agent API endpoints |
| `constants.py` | Runtime constants (`AGENT_SERVICE_URL`, endpoint URLs, `UPLOADS_DIR`) |
| `processing.py` | Claim submit/poll orchestration that mutates `st.session_state` |
| `state.py` | Session-state initialization/reset/update helpers |
| `result_utils.py` | Agent-result normalization + decision UI helpers |
| `render_sidebar.py` | Sidebar and service status rendering |
| `render_human_review.py` | Human-in-the-loop review screen rendering |
| `render_results.py` | Final results dashboard and agent cards |
| `ui_models.py` | UI dataclasses for lightweight view models |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Keep this layer UI-only; do not move business logic from API/workflow into Streamlit.
- Prefer adding new rendering logic to dedicated `render_*.py` modules instead of growing `app.py`.
- Keep API calls centralized in `api_client.py`.
- Keep shared `st.session_state` key defaults in `state.py`.
- Use `UPLOADS_DIR`/URL constants from `constants.py` to avoid endpoint drift.

### Testing Requirements

- Manual UI smoke test: `streamlit run interfaces/web/app.py`
- Backend integration checks:
  - `POST /api/v1/multi-agent/process`
  - `GET /api/v1/multi-agent/status/{claim_id}`
  - `POST /api/v1/multi-agent/submit-review/{claim_id}`
- For code-level sanity: `python -m compileall interfaces/web`

### Common Patterns

- **Session State**: initialize via `init_session_state()`, clear with `reset_state()` and `clear_review_edit_state()`.
- **Polling Loop**: `poll_claim_status()` updates current step/status and drives reruns.
- **Renderer Split**: heavy UI sections live in dedicated renderer modules (`render_*`).
- **Error Handling**: catch `requests.exceptions.RequestException` close to UI actions and surface via `st.session_state.error`.
- **File Upload Contract**: send filename only to backend after saving upload under `UPLOADS_DIR`.

## Dependencies

### Internal

- `interfaces/web/api_client.py`
- `interfaces/web/constants.py`
- `interfaces/web/processing.py`
- `interfaces/web/state.py`
- `interfaces/web/result_utils.py`

### External

- `streamlit` - UI framework
- `requests` - HTTP client
- `python-dotenv` - env loading (through `constants.py`)
- Standard library: `json`, `time`, `typing`, `os`

<!-- MANUAL: -->
