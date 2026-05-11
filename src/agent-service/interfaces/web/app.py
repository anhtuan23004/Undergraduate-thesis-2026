"""Streamlit UI for insurance claims workflow with HITL review."""

from __future__ import annotations

import streamlit as st
from app_actions import handle_new_claim, handle_select_run, handle_url_change
from app_rendering import render_main_content
from app_session import init_session_state
from components import (
    render_app_header,
    render_brand_theme,
    render_raw_state,
    render_sidebar,
)


def main() -> None:
    """Streamlit app entry point."""
    st.set_page_config(
        page_title="Hệ thống bồi thường bảo hiểm",
        page_icon=":material/health_and_safety:",
        layout="wide",
    )

    init_session_state()
    render_brand_theme()

    render_sidebar(
        on_new_claim=handle_new_claim,
        on_select_run=handle_select_run,
        current_run_id=st.session_state.current_run_id,
        run_history=st.session_state.run_history,
        api_url=st.session_state.api_base_url,
        on_url_change=handle_url_change,
    )

    render_app_header(
        current_run_id=st.session_state.current_run_id,
        api_url=st.session_state.api_base_url,
    )

    render_main_content()

    if st.toggle("Chế độ developer", key="developer_mode") and st.session_state.workflow_state_data:
        render_raw_state(st.session_state.workflow_state_data)


if __name__ == "__main__":
    main()
