"""Final decision dashboard components."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from .document_view import render_document_tab_link
from .history import render_history_log


def render_final_dashboard(state_data: dict) -> None:
    """Step 4: final decision card, details, and audit trail."""
    st.subheader(":material/gavel: Bước 4 - Kết quả cuối cùng")
    render_document_tab_link(state_data)
    final_result = state_data.get("final_result") or {}

    decision = str(final_result.get("decision") or "").lower()
    approved_amount = final_result.get("approved_amount") or 0
    message = final_result.get("message") or final_result.get("rejection_reason") or "-"

    with st.container(border=True):
        if decision == "approve":
            st.success("PHÊ DUYỆT")
        else:
            st.error("TỪ CHỐI")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Số tiền bồi thường", f"{approved_amount:,}")
        with col2:
            st.write("**Lý do / diễn giải**")
            st.write(message)

        issues_summary = final_result.get("issues_summary") or []
        if issues_summary:
            st.markdown("**Tổng hợp vấn đề**")
            st.dataframe(pd.DataFrame(issues_summary), hide_index=True, use_container_width=True)

    st.markdown("**Audit trail toàn quy trình**")
    render_history_log(state_data.get("history", []))

    st.download_button(
        ":material/download: Tải báo cáo kết quả (JSON)",
        data=json.dumps(state_data, ensure_ascii=False, indent=2),
        file_name=f"claim_report_{state_data.get('run_id', 'unknown')}.json",
        mime="application/json",
        use_container_width=True,
    )
