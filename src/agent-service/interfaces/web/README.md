# Streamlit Web Interface

Interactive UI for demonstrating the Insurance Claims Processing Multi-Agent System with Human-in-the-Loop capabilities.

## Project Structure

```
interfaces/web/
├── app.py          # Main Streamlit entry point
├── api_client.py   # API client functions
├── components.py  # UI components
└── README.md       # This file
```

## Components

### api_client.py

API client for communicating with the agent service backend.

| Function | Description |
|---------|-------------|
| `start_workflow()` | POST to `/api/v1/workflows/run` |
| `get_workflow_status()` | GET from `/api/v1/workflows/status/{run_id}` |
| `resume_workflow()` | POST to `/api/v1/workflows/resume/{run_id}` |

### components.py

Reusable Streamlit UI components.

| Function | Description |
|---------|-------------|
| `render_sidebar()` | Session management, run history |
| `render_claim_input_form()` | OCR data input form |
| `render_workflow_status()` | Agent progress dashboard |
| `render_hitl_panel()` | Human-in-the-Loop review panel |
| `render_raw_state()` | Developer mode (raw GraphState) |

### app.py

Main application entry point. Orchestrates components and manages session state.

## Features

### 1. Sidebar - Session Management

- **➕ New Claim**: Create new processing session
- **📋 Run History**: View and select previous sessions
- **Status Indicators**:
  - 🟢 Completed
  - 🟡 Pending Human Review
  - 🔵 Running
  - 🔴 Error

### 2. Claim Input Form

- Claim ID and Policy Number
- Insurance type (Health, Dental, Vision, Life)
- Task type (full-flow, med-verification, etc.)
- JSON OCR data input
- 🚀 Start Workflow button

### 3. Workflow Status Dashboard

- Visual progress through 3 agents:
  - Agent 1: Completeness Check 📋
  - Agent 2: Medical Quality 🏥
  - Agent 3: Final Decision ✅
- Agent result cards with decisions
- Issue severity indicators

### 4. Human-in-the-Loop Panel

- ⚠️ Warning alert
- Decision options (Approve/Reject/Edit)
- Notes field
- ⚡ Resume workflow

### 5. Developer Mode

- Raw GraphState viewer

## Running

```bash
# Terminal 1: Start agent service
cd src/agent-service
uvicorn main:app --reload --port 8003

# Terminal 2: Start Streamlit UI
cd src/agent-service/interfaces/web
streamlit run app.py --server.port 8501
```

## API Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/workflows/run` | POST | Start new workflow |
| `/api/v1/workflows/resume/{run_id}` | POST | Resume after HITL |
| `/api/v1/workflows/status/{run_id}` | GET | Get workflow status |

## Session State

| Variable | Description |
|----------|-------------|
| `current_run_id` | Active thread/run ID |
| `workflow_state_data` | Cached workflow state |
| `is_waiting_human` | HITL panel visibility |
| `run_history` | List of previous runs |
| `api_base_url` | Backend API URL |
