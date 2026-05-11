"""Streamlit session state helpers for the web UI."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from api_client import create_client

DEFAULT_API_URL = "http://localhost:8003"


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    defaults = {
        "current_run_id": None,
        "workflow_state_data": None,
        "run_history": [],
        "api_base_url": DEFAULT_API_URL,
        "client": None,
        "auto_poll_enabled": True,
        "workflow_action_lock": False,
        "paused_continue_button_disabled": False,
        "pending_paused_continue_request": False,
        "refresh_in_flight": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_client():
    """Get or create API client from current base URL."""
    if st.session_state.client is None:
        st.session_state.client = create_client(st.session_state.api_base_url)
    return st.session_state.client


def reset_workflow_flags() -> None:
    """Clear workflow action flags after run switching or reset."""
    st.session_state.paused_continue_button_disabled = False
    st.session_state.pending_paused_continue_request = False
    st.session_state.refresh_in_flight = False
    st.session_state.workflow_action_lock = False


def upsert_run_history(run_id: str | None, claim_id: str | None, payload: dict) -> None:
    """Insert or update run history row by run_id."""
    if not run_id:
        return

    for item in st.session_state.run_history:
        if item.get("run_id") == run_id:
            item["data"] = payload
            item["updated_at"] = datetime.now().isoformat()
            return

    st.session_state.run_history.append(
        {
            "run_id": run_id,
            "claim_id": claim_id or payload.get("claim_id"),
            "timestamp": datetime.now().isoformat(),
            "data": payload,
        }
    )
