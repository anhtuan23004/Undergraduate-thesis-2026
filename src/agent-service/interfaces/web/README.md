# Streamlit Web Interface

Interactive Streamlit UI for demonstrating the insurance claims processing workflow with Human-in-the-Loop review.

## Project Structure

Current workspace layout:

```text
interfaces/web/
├── app.py          # Streamlit entry point, session state, workflow actions, SSE handling
├── api_client.py   # HTTP/SSE client for the agent-service API
├── components.py   # Reusable rendering helpers and UI state formatters
└── README.md       # This file
```

`app.py` owns orchestration and action handlers. `components.py` owns rendering, timeline formatting, review panels, findings tables, final dashboard, and error details.

## Backend API Flow

The UI uses the API in this order:

1. `POST /api/v1/workflows/upload`
   Uploads a PDF/image claim document and receives `file_path` plus `file_hash`.
2. `POST /api/v1/workflows/run-stream`
   Starts a workflow and streams progress with server-sent events.
3. `GET /api/v1/workflows/status/{run_id}`
   Refreshes the latest graph state.
4. `POST /api/v1/workflows/resume/{run_id}`
   Submits a human review decision.
5. `POST /api/v1/workflows/continue/{run_id}`
   Continues a workflow paused at a non-human node.

Upload validation is enforced by the backend:

- Extensions: `.pdf`, `.png`, `.jpg`, `.jpeg`
- MIME types: `application/pdf`, `image/png`, `image/jpeg`
- Size: `MAX_UPLOAD_SIZE_MB`
- Stored path: must remain inside `UPLOADS_DIR`

## Components

### `api_client.py`

| Function | Description |
|----------|-------------|
| `upload_document()` | Multipart upload to `/api/v1/workflows/upload` |
| `start_workflow_stream()` | POST to `/api/v1/workflows/run-stream` and yield SSE events |
| `stream_events()` | GET from `/api/v1/workflows/stream/{run_id}` and yield SSE events |
| `get_workflow_status()` | GET from `/api/v1/workflows/status/{run_id}` |
| `resume_workflow()` | POST to `/api/v1/workflows/resume/{run_id}` |
| `continue_workflow()` | POST to `/api/v1/workflows/continue/{run_id}` |
| `health_check()` | GET from `/api/v1/health` |

### `components.py`

| Function | Description |
|----------|-------------|
| `render_brand_theme()` | Inject app styling |
| `get_ui_state()` | Convert graph state into `processing`, `waiting_for_human`, `error`, or `completed` |
| `render_sidebar()` | API URL, auto-poll toggle, run history, new-claim action |
| `render_claim_submission()` | Claim ID, policy number, and document upload form |
| `render_monitoring()` | Current status metrics, timeline, step messages, history |
| `render_human_review_panel()` | Human decision form with optional JSON edit |
| `render_final_dashboard()` | Final decision summary and downloadable JSON report |
| `render_error_state()` | Structured API/workflow error details |
| `render_raw_state()` | Developer raw graph state viewer |

### `app.py`

`app.py` ties the UI together:

- Initializes Streamlit session state
- Creates and refreshes the `APIClient`
- Uploads documents before workflow start
- Consumes SSE events from `run-stream` and `stream/{run_id}`
- Maintains run history
- Locks resume/continue actions to avoid duplicate calls on rerun
- Auto-polls only while the workflow is actively processing

## Features

- Document upload with backend validation
- Live SSE progress updates
- Explicit 5-step timeline:
  - Completeness check
  - Agent review
  - Quality check
  - Human review
  - Final decision
- Human review actions: approve, reject, edit
- Structured findings, evidence, suggested updates, and audit history
- Developer mode for raw graph state inspection

## Running

```bash
# Terminal 1: start the agent service
cd src/agent-service
uvicorn main:app --reload --port 8003

# Terminal 2: start the Streamlit UI
cd src/agent-service/interfaces/web
streamlit run app.py --server.port 8501
```

If the browser reports `Failed to fetch dynamically imported module` after code changes, restart Streamlit and hard-refresh the browser tab. The error is usually caused by a stale Streamlit JavaScript bundle in the browser cache.

## Session State

| Variable | Description |
|----------|-------------|
| `current_run_id` | Active workflow run ID |
| `workflow_state_data` | Cached latest workflow state |
| `run_history` | Recent runs for sidebar switching |
| `api_base_url` | Backend API base URL |
| `client` | Cached `APIClient` instance |
| `auto_poll_enabled` | Whether processing states refresh automatically |
| `workflow_action_lock` | Prevents duplicate resume/continue actions |
| `paused_continue_button_disabled` | Disables pause-continue button after click |
| `pending_paused_continue_request` | Triggers one continue request on rerun |
| `refresh_in_flight` | Prevents duplicate status refreshes |

## UI State Mapping

The UI derives page state from explicit workflow fields:

| API state | UI behavior |
|-----------|-------------|
| `workflow_status="running"` | Show monitoring and optional auto-polling |
| `workflow_status="waiting_human"` or `pending_human_review=true` | Show human review panel |
| `workflow_status="completed"` or `final_result` exists | Show final dashboard |
| `workflow_status="error"` or `error` exists | Show structured error panel |

## Verification

Focused UI helper tests:

```bash
python -m pytest src/agent-service/tests/test_web_components.py -q
```

General frontend lint target:

```bash
python -m ruff check src/agent-service/interfaces/web
```
