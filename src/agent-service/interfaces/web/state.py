"""Session state helpers for Streamlit UI."""

from datetime import datetime
from typing import Dict, Optional

import streamlit as st

SESSION_DEFAULTS = {
    "claim_id": "",
    "policy_number": "",
    "uploaded_file": None,
    "processing": False,
    "result": None,
    "error": None,
    "current_step": "idle",
    "processing_history": [],
    "service_available": None,
    "status_checking": False,
    "pending_review": False,
    "claim_status": None,
    "status_data": None,
}

REVIEW_EDIT_KEYS = ["edited_agent_1", "edited_agent_2", "enable_editing"]


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_state() -> None:
    """Reset the session state to initial values."""
    for key, value in SESSION_DEFAULTS.items():
        st.session_state[key] = value
    clear_review_edit_state()


def update_step(
    step: str, status: str = "in_progress", details: Optional[Dict] = None
) -> None:
    """Update the current processing step and append to history."""
    st.session_state.current_step = step
    st.session_state.processing_history.append(
        {
            "step": step,
            "status": status,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "details": details or {},
        }
    )


def clear_review_edit_state() -> None:
    """Clear temporary human-review editing keys from session state."""
    for key in REVIEW_EDIT_KEYS:
        if key in st.session_state:
            del st.session_state[key]
