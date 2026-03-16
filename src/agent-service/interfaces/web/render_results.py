"""Result dashboard rendering for Streamlit UI."""

from typing import Any, Dict

import streamlit as st

from result_utils import (
    get_decision_color,
    get_decision_emoji,
    normalize_agent_result,
    normalize_run_output,
)
from state import reset_state


def render_agent_result_card(title: str, result: Dict[str, Any], icon: str) -> None:
    """Render a card displaying agent result details."""
    if not result:
        st.info(f"{icon} {title}: No data available")
        return

    decision = result.get("decision", "N/A")
    confidence = result.get("confidence", 0.0)
    reasoning = result.get("reasoning", "No reasoning provided")
    issues = result.get("issues", [])
    missing_docs = result.get("missing_documents", [])

    if decision.lower() == "accept":
        border_color = "#28a745"
        bg_color = "#d4edda"
    elif decision.lower() == "reject":
        border_color = "#dc3545"
        bg_color = "#f8d7da"
    else:
        border_color = "#ffc107"
        bg_color = "#fff3cd"

    with st.expander(f"{icon} {title}", expanded=True):
        st.markdown(
            f"""
            <div style="
                background-color: {bg_color};
                border-left: 4px solid {border_color};
                padding: 1rem;
                border-radius: 0.25rem;
                margin-bottom: 1rem;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>Decision:</strong>
                        <span style="
                            background-color: {border_color};
                            color: white;
                            padding: 0.25rem 0.5rem;
                            border-radius: 0.25rem;
                            margin-left: 0.5rem;
                        ">{decision.upper()}</span>
                    </div>
                    <div>
                        <strong>Confidence:</strong> {confidence:.1%}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Reasoning:**")
        st.markdown(f"{reasoning}")

        if issues:
            st.markdown("**Issues Found:**")
            for issue in issues:
                severity = issue.get("severity", "medium")
                description = issue.get("description", "")
                field = issue.get("field", "")

                severity_colors = {
                    "critical": "#dc3545",
                    "high": "#fd7e14",
                    "medium": "#ffc107",
                    "low": "#17a2b8",
                }
                severity_color = severity_colors.get(severity.lower(), "#6c757d")

                st.markdown(
                    f"""
                    <div style="
                        background-color: #f8f9fa;
                        border-left: 3px solid {severity_color};
                        padding: 0.5rem;
                        margin: 0.5rem 0;
                        border-radius: 0.25rem;
                    ">
                        <span style="
                            background-color: {severity_color};
                            color: white;
                            padding: 0.1rem 0.4rem;
                            border-radius: 0.2rem;
                            font-size: 0.75rem;
                            text-transform: uppercase;
                        ">{severity}</span>
                        <span style="margin-left: 0.5rem;">{description}</span>
                        {f'<span style="color: #6c757d; font-size: 0.85rem;">(Field: {field})</span>' if field else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if missing_docs:
            st.markdown("**Missing Documents:**")
            for doc in missing_docs:
                st.markdown(f"- ❌ {doc}")


def render_results_dashboard() -> None:
    """Render the results dashboard with final decision and agent details."""
    if not st.session_state.result:
        return

    st.header("📊 Processing Results")

    result = normalize_run_output(st.session_state.result)
    claim_id = result.get("claim_id", st.session_state.claim_id or "Unknown")

    final_result_raw = result.get("final_result") or {}
    final_decision = (
        final_result_raw.get("decision", "").upper()
        or final_result_raw.get("final_decision", "").upper()
    )
    if not final_decision:
        agent1 = result.get("agent_1_result") or {}
        human = result.get("human_review_result") or {}
        if human.get("decision") == "approve":
            final_decision = "APPROVE"
        elif human.get("decision") == "reject":
            final_decision = "REJECT"
        elif not agent1.get("valid", True):
            final_decision = "REJECT"
        else:
            final_decision = "PENDING"

    decision_color = get_decision_color(final_decision)
    decision_emoji = get_decision_emoji(final_decision)

    st.markdown(
        f"""
        <div style="
            background-color: {decision_color};
            color: white;
            padding: 1.5rem;
            border-radius: 0.5rem;
            text-align: center;
            margin-bottom: 2rem;
        ">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">{decision_emoji}</div>
            <div style="font-size: 1.2rem; opacity: 0.9;">Claim ID: {claim_id}</div>
            <div style="font-size: 2rem; font-weight: bold;">Final Decision: {final_decision}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Agent Details")

    col1, col2 = st.columns(2)

    with col1:
        render_agent_result_card(
            "Agent 1: Completeness Check",
            normalize_agent_result(result.get("agent_1_result")),
            "📄",
        )

    with col2:
        render_agent_result_card(
            "Agent 2: Quality Check",
            normalize_agent_result(result.get("agent_2_result")),
            "🔍",
        )

    human_review = result.get("human_review_result")
    if human_review:
        st.subheader("👤 Human Review")
        render_agent_result_card(
            "Human Review Result",
            normalize_agent_result(human_review),
            "👤",
        )

    st.subheader("📜 Processing Timeline")
    processing_steps = result.get("processing_steps", [])
    if not processing_steps:
        if result.get("agent_1_result"):
            processing_steps.append({"step": "Completeness Check", "status": "completed"})
        if result.get("agent_2_result"):
            processing_steps.append({"step": "Quality Check", "status": "completed"})
        if result.get("human_review_result"):
            processing_steps.append({"step": "Human Review", "status": "completed"})
        if final_decision not in ("PENDING", ""):
            processing_steps.append({"step": "Final Decision", "status": "completed"})

    if processing_steps:
        for idx, step in enumerate(processing_steps):
            step_name = step.get("step", f"Step {idx + 1}")
            step_status = step.get("status", "unknown")

            status_emoji = {
                "completed": "✅",
                "in_progress": "⏳",
                "pending": "⏸️",
                "failed": "❌",
            }.get(step_status, "❓")

            st.markdown(
                f"""
                <div style="
                    display: flex;
                    align-items: center;
                    padding: 0.5rem;
                    border-left: 2px solid #dee2e6;
                    margin-left: 1rem;
                    margin-bottom: 0.5rem;
                ">
                    <span style="margin-right: 0.5rem;">{status_emoji}</span>
                    <span style="font-weight: 500;">{step_name}</span>
                    <span style="margin-left: auto; color: #6c757d; font-size: 0.85rem;">
                        {step_status.upper()}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No processing history available")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Submit Another Claim", use_container_width=True):
            reset_state()
            st.rerun()
    with col2:
        if st.button("📥 Export Results", use_container_width=True):
            st.download_button(
                label="Download JSON",
                data=str(result),
                file_name=f"claim_{claim_id}_result.json",
                mime="application/json",
            )
