"""History table rendering and pure history formatters."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .formatters import format_history_label as _format_history_label
from .formatters import friendly_status, friendly_step_name

format_history_label = _format_history_label


def render_history_log(history: list[dict]) -> None:
    """Render completed actions from graph history list."""
    st.markdown("**Nhật ký hành động**")
    if not history:
        st.caption("Chưa có lịch sử")
        return

    rows = []
    for idx, item in enumerate(history, start=1):
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        step_raw = str(item.get("step") or "unknown")
        step_label = friendly_step_name(step_raw)

        decision = item.get("decision") or result.get("decision") or result.get("status") or "-"
        status = friendly_status(decision, result)

        message = (
            result.get("message")
            or result.get("rejection_reason")
            or item.get("notes")
            or result.get("error")
            or "-"
        )

        issues = result.get("issues") or result.get("issues_summary") or []
        issue_count = len(issues) if isinstance(issues, list) else 0

        rows.append(
            {
                "STT": idx,
                "Bước": step_label,
                "Tác nhân": item.get("agent", "System"),
                "Trạng thái": status,
                "Quyết định": str(decision).upper() if decision != "-" else "-",
                "Số lỗi": issue_count,
                "Thông điệp": message,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "STT": st.column_config.NumberColumn("STT", width="small"),
            "Bước": st.column_config.TextColumn("Bước", width="medium"),
            "Tác nhân": st.column_config.TextColumn("Tác nhân", width="small"),
            "Trạng thái": st.column_config.TextColumn("Trạng thái", width="small"),
            "Quyết định": st.column_config.TextColumn("Quyết định", width="small"),
            "Số lỗi": st.column_config.NumberColumn("Số lỗi", width="small"),
            "Thông điệp": st.column_config.TextColumn("Thông điệp", width="large"),
        },
    )


_friendly_step_name = friendly_step_name
_friendly_status = friendly_status
