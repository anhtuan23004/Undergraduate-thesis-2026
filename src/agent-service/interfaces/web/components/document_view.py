"""Document preview link helpers."""

from __future__ import annotations

from html import escape
from urllib.parse import quote

import streamlit as st


def workflow_document_url(state_data: dict) -> str | None:
    """Build a document preview URL for the active workflow run."""
    run_id = state_data.get("run_id")
    if not run_id:
        return None

    base_url = str(st.session_state.get("api_base_url", "")).rstrip("/")
    if not base_url:
        return None

    return f"{base_url}/api/v1/workflows/document/{quote(str(run_id), safe='')}"


def render_document_tab_link(state_data: dict) -> None:
    """Render a link that opens the source document in a new browser tab."""
    url = workflow_document_url(state_data)
    if not url:
        return

    st.markdown(
        (
            f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            "Mở tài liệu trong tab mới"
            "</a>"
        ),
        unsafe_allow_html=True,
    )
