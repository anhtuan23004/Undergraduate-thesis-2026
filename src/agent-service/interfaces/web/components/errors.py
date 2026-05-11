"""Error rendering components."""

from __future__ import annotations

import streamlit as st


def render_error_state(
    error_message: str,
    error_payload: dict | None = None,
    context_label: str = "workflow",
) -> None:
    """Render API/workflow error with full details for human review."""
    st.error(f"Lỗi {context_label}: {error_message}")

    with st.container(border=True):
        st.markdown("**Chi tiết lỗi cho Human Review**")

        status_code = None
        endpoint = None
        detail = None
        if isinstance(error_payload, dict):
            status_code = error_payload.get("status_code")
            endpoint = error_payload.get("endpoint")
            detail = error_payload.get("error_detail") or error_payload.get("detail")

        col1, col2 = st.columns(2)
        with col1:
            st.caption("Mã lỗi HTTP")
            st.write(str(status_code) if status_code is not None else "-")
        with col2:
            st.caption("Endpoint")
            st.write(endpoint or "-")

        st.caption("Thông tin chi tiết")
        if detail:
            if isinstance(detail, dict | list):
                st.json(detail)
            else:
                st.code(str(detail), language="text")
        else:
            st.write(error_message)

        if isinstance(error_payload, dict):
            with st.expander("Xem payload lỗi đầy đủ"):
                st.json(error_payload)
