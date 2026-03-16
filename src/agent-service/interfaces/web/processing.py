"""Claim processing orchestration helpers for Streamlit UI."""

import os
from typing import Any

import requests
import streamlit as st

from api_client import get_claim_status, submit_claim
from constants import UPLOADS_DIR
from state import update_step


def poll_claim_status() -> None:
    """Poll the current claim status and update session state."""
    claim_id = st.session_state.claim_id
    if not claim_id:
        return

    try:
        status_data = get_claim_status(claim_id)
    except requests.exceptions.RequestException as exc:
        st.session_state.error = f"Status check error: {exc}"
        return

    if status_data is None:
        return

    st.session_state.status_data = status_data
    status = status_data.get("status", "unknown")
    st.session_state.claim_status = status

    if status == "interrupted":
        st.session_state.status_checking = False
        st.session_state.pending_review = True
        st.session_state.current_step = "human_review"
        update_step("human_review", "in_progress", status_data)
    elif status == "finished":
        st.session_state.status_checking = False
        st.session_state.pending_review = False
        st.session_state.result = status_data
        st.session_state.current_step = "completed"
        update_step("final_decision", "completed", status_data)
    elif status == "error":
        st.session_state.status_checking = False
        st.session_state.pending_review = False
        st.session_state.error = status_data.get("error", "Unknown error occurred")
        st.session_state.current_step = "error"
    else:
        st.session_state.pending_review = False
        if status_data.get("agent_2_result"):
            st.session_state.current_step = "quality_check"
        elif status_data.get("agent_1_result"):
            st.session_state.current_step = "completeness_check"
        else:
            st.session_state.current_step = "start"


def start_claim_processing() -> None:
    """Save uploaded file and submit claim for processing."""
    try:
        update_step("start", "in_progress")

        uploaded_file = st.session_state.uploaded_file
        if uploaded_file is None:
            raise ValueError("No file uploaded")

        os.makedirs(UPLOADS_DIR, exist_ok=True)

        file_name = uploaded_file.name
        file_path = os.path.join(UPLOADS_DIR, file_name)
        with open(file_path, "wb") as file_obj:
            file_obj.write(uploaded_file.getvalue())

        submit_claim(
            claim_id=st.session_state.claim_id,
            policy_number=st.session_state.policy_number,
            file_path=file_name,
        )

        st.session_state.processing = False
        st.session_state.status_checking = True
        st.session_state.error = None

        if os.path.exists(file_path):
            os.remove(file_path)

    except requests.exceptions.ConnectionError:
        st.session_state.error = "Cannot connect to agent service. Please ensure it's running."
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
        st.session_state.service_available = False
    except requests.exceptions.Timeout:
        st.session_state.error = "Request timed out. The service may be busy."
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
    except requests.exceptions.HTTPError as exc:
        st.session_state.error = f"API Error: {exc.response.status_code} - {exc.response.text}"
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
    except Exception as exc:  # noqa: BLE001 - surface full UI error for dev diagnostics
        st.session_state.error = f"Unexpected error: {str(exc)}"
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
