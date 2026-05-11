"""SSE stream handling for the Streamlit web UI."""

from __future__ import annotations

from collections.abc import Iterable

import streamlit as st
from components import STEP_LABELS, render_error_state


def consume_stream_events(
    event_iter: Iterable[tuple[str, dict]],
    status_label: str = "Đang xử lý...",
) -> dict | None:
    """Display SSE stream events via st.status and return final state."""
    status = st.status(status_label, expanded=True)
    last_state = None

    for event_type, payload in event_iter:
        if event_type == "run_started":
            run_id = payload.get("run_id")
            st.session_state.current_run_id = run_id
            status.write(f"🚀 Workflow khởi tạo — run_id: `{run_id[:8]}`")

        elif event_type == "node_start":
            step_label = STEP_LABELS.get(payload.get("step"), payload.get("node", ""))
            status.write(f"⏳ Đang xử lý: **{step_label}**...")

        elif event_type == "node_end":
            step_label = STEP_LABELS.get(payload.get("step"), payload.get("node", ""))
            status.write(f"✅ Hoàn thành: **{step_label}**")
            last_state = payload.get("state", last_state)
            if last_state:
                st.session_state.workflow_state_data = last_state

        elif event_type == "done":
            last_state = payload
            status.update(label="Xử lý hoàn tất!", state="complete", expanded=False)

        elif event_type == "error":
            status.update(label="Lỗi xử lý!", state="error")
            render_error_state(
                payload.get("error", "Unknown streaming error"),
                error_payload=payload,
                context_label="stream workflow",
            )
            return None

    return last_state
