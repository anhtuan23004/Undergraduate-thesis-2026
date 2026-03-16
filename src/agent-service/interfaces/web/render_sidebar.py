"""Sidebar rendering for Streamlit UI."""

import requests
import streamlit as st

from api_client import check_service_health, get_pending_reviews
from constants import AGENT_SERVICE_URL


def render_service_status() -> None:
    """Render the service availability status indicator."""
    if st.session_state.service_available is None:
        st.session_state.service_available = check_service_health()

    if st.session_state.service_available:
        st.sidebar.success("✅ Agent Service: Online")
    else:
        st.sidebar.error("❌ Agent Service: Offline")
        st.sidebar.info(f"Expected at: {AGENT_SERVICE_URL}")


def render_sidebar() -> None:
    """Render the sidebar with information and settings."""
    st.sidebar.title("ℹ️ About")
    st.sidebar.info(
        """
        This application provides a user interface for the Insurance Claims
        Processing multi-agent system with human-in-the-loop support.

        **Workflow:**
        1. Completeness Check
        2. Quality Check
        3. Human Review (if needed)
        4. Final Decision
        """
    )

    st.sidebar.divider()

    st.sidebar.subheader("⚙️ Configuration")
    st.sidebar.text_input(
        "Agent Service URL",
        value=AGENT_SERVICE_URL,
        disabled=True,
        help="Configure via AGENT_SERVICE_URL environment variable",
    )

    render_service_status()

    st.sidebar.divider()

    st.sidebar.subheader("📊 Statistics")
    st.sidebar.metric(
        label="Total Submissions",
        value=len(st.session_state.processing_history),
    )

    if st.session_state.service_available:
        st.sidebar.divider()
        st.sidebar.subheader("⏳ Pending Reviews")
        if st.sidebar.button("Refresh Pending List"):
            try:
                pending = get_pending_reviews()
            except requests.exceptions.RequestException as exc:
                st.session_state.error = f"Pending reviews error: {exc}"
                pending = []
            if pending:
                for item in pending:
                    claim_id = item.get("claim_id", "Unknown")
                    policy = item.get("policy_number", "")
                    submitted = item.get("submitted_at", "")
                    label = f"**{claim_id}**"
                    if policy:
                        label += f" | Policy: {policy}"
                    if submitted:
                        label += f" | {submitted[:10]}"
                    st.sidebar.info(label)
            else:
                st.sidebar.success("No pending reviews")
