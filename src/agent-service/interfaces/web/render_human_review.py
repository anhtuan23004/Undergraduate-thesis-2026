"""Human review UI rendering for interrupted claims."""

import json
import time
from typing import Any, Dict

import requests
import streamlit as st

from api_client import submit_human_review
from state import clear_review_edit_state


def render_human_review_interface() -> None:
    """Render the human review interface for interrupted claims."""
    status_data = st.session_state.status_data or {}
    agent_results = status_data.get("agent_results", {})
    claim_id = st.session_state.claim_id

    st.header("👤 Human Review Required")

    st.warning(
        f"⚠️ Claim **{claim_id}** has been flagged for human review. "
        "Please review the agent findings below and provide your decision."
    )

    st.subheader("Agent Findings (Editable)")

    if "edited_agent_1" not in st.session_state:
        agent1_original = agent_results.get("agent_1", {})
        st.session_state.edited_agent_1 = {
            "decision": agent1_original.get("decision", "accept"),
            "confidence": float(agent1_original.get("confidence", 0.8)),
            "reasoning": agent1_original.get("reasoning", ""),
            "issues": agent1_original.get("issues", []),
        }
    if "edited_agent_2" not in st.session_state:
        agent2_original = agent_results.get("agent_2", {})
        st.session_state.edited_agent_2 = {
            "decision": agent2_original.get("decision", "accept"),
            "confidence": float(agent2_original.get("confidence", 0.8)),
            "reasoning": agent2_original.get("reasoning", ""),
            "issues": agent2_original.get("issues", []),
        }
    if "enable_editing" not in st.session_state:
        st.session_state.enable_editing = False

    enable_editing = st.checkbox(
        "✏️ Enable Editing of Agent Results",
        value=st.session_state.enable_editing,
        help="Check this to modify agent decisions, confidence, and reasoning before submission",
    )
    st.session_state.enable_editing = enable_editing

    col1, col2 = st.columns(2)

    with col1:
        with st.expander("📄 Agent 1: Completeness Check", expanded=True):
            agent1_data = agent_results.get("agent_1", {})
            if agent1_data:
                if enable_editing:
                    st.markdown("**Edit Agent 1 Results:**")
                    st.session_state.edited_agent_1["decision"] = st.selectbox(
                        "Decision",
                        options=["accept", "reject", "accept_with_edit"],
                        index=["accept", "reject", "accept_with_edit"].index(
                            st.session_state.edited_agent_1.get("decision", "accept")
                        ),
                        key="agent1_decision",
                    )
                    st.session_state.edited_agent_1["confidence"] = st.slider(
                        "Confidence",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(st.session_state.edited_agent_1.get("confidence", 0.8)),
                        step=0.05,
                        key="agent1_confidence",
                    )
                    st.session_state.edited_agent_1["reasoning"] = st.text_area(
                        "Reasoning",
                        value=st.session_state.edited_agent_1.get("reasoning", ""),
                        height=80,
                        key="agent1_reasoning",
                    )

                    st.markdown("**Issues:**")
                    issues_json = st.text_area(
                        "Issues (JSON format)",
                        value=str(st.session_state.edited_agent_1.get("issues", [])),
                        height=60,
                        key="agent1_issues",
                    )
                    try:
                        st.session_state.edited_agent_1["issues"] = json.loads(
                            issues_json.replace("'", '"')
                        )
                    except json.JSONDecodeError:
                        st.session_state.edited_agent_1["issues"] = []

                    st.divider()
                    st.markdown("**Preview of Edited Result:**")

                display_data: Dict[str, Any] = (
                    st.session_state.edited_agent_1 if enable_editing else agent1_data
                )
                st.markdown(f"**Decision:** `{display_data.get('decision', 'N/A')}`")
                st.markdown(f"**Confidence:** {display_data.get('confidence', 0.0):.1%}")
                st.markdown(
                    f"**Reasoning:** {display_data.get('reasoning', 'No reasoning provided')}"
                )

                issues = display_data.get("issues", [])
                if issues:
                    st.markdown("**Issues Found:**")
                    for issue in issues:
                        severity = (
                            issue.get("severity", "medium")
                            if isinstance(issue, dict)
                            else "medium"
                        )
                        description = (
                            issue.get("description", str(issue))
                            if isinstance(issue, dict)
                            else str(issue)
                        )
                        st.markdown(f"- **{str(severity).upper()}:** {description}")
            else:
                st.info("No completeness check data available")

    with col2:
        with st.expander("🔍 Agent 2: Quality Check", expanded=True):
            agent2_data = agent_results.get("agent_2", {})
            if agent2_data:
                if enable_editing:
                    st.markdown("**Edit Agent 2 Results:**")
                    st.session_state.edited_agent_2["decision"] = st.selectbox(
                        "Decision",
                        options=["accept", "reject", "accept_with_edit"],
                        index=["accept", "reject", "accept_with_edit"].index(
                            st.session_state.edited_agent_2.get("decision", "accept")
                        ),
                        key="agent2_decision",
                    )
                    st.session_state.edited_agent_2["confidence"] = st.slider(
                        "Confidence",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(st.session_state.edited_agent_2.get("confidence", 0.8)),
                        step=0.05,
                        key="agent2_confidence",
                    )
                    st.session_state.edited_agent_2["reasoning"] = st.text_area(
                        "Reasoning",
                        value=st.session_state.edited_agent_2.get("reasoning", ""),
                        height=80,
                        key="agent2_reasoning",
                    )

                    st.markdown("**Issues:**")
                    issues_json = st.text_area(
                        "Issues (JSON format)",
                        value=str(st.session_state.edited_agent_2.get("issues", [])),
                        height=60,
                        key="agent2_issues",
                    )
                    try:
                        st.session_state.edited_agent_2["issues"] = json.loads(
                            issues_json.replace("'", '"')
                        )
                    except json.JSONDecodeError:
                        st.session_state.edited_agent_2["issues"] = []

                    st.divider()
                    st.markdown("**Preview of Edited Result:**")

                display_data = st.session_state.edited_agent_2 if enable_editing else agent2_data
                st.markdown(f"**Decision:** `{display_data.get('decision', 'N/A')}`")
                st.markdown(f"**Confidence:** {display_data.get('confidence', 0.0):.1%}")
                st.markdown(
                    f"**Reasoning:** {display_data.get('reasoning', 'No reasoning provided')}"
                )

                issues = display_data.get("issues", [])
                if issues:
                    st.markdown("**Issues Found:**")
                    for issue in issues:
                        severity = (
                            issue.get("severity", "medium")
                            if isinstance(issue, dict)
                            else "medium"
                        )
                        description = (
                            issue.get("description", str(issue))
                            if isinstance(issue, dict)
                            else str(issue)
                        )
                        st.markdown(f"- **{str(severity).upper()}:** {description}")
            else:
                st.info("No quality check data available")

    st.divider()

    st.subheader("Your Decision")

    with st.form("human_review_form"):
        feedback = st.text_area(
            "Feedback / Notes",
            placeholder="Enter your feedback, reasoning, or requested changes...",
            height=120,
            help="Your feedback will be recorded with your decision",
        )

        reviewed_by = st.text_input(
            "Reviewer Name",
            placeholder="Your name",
            value="Human Reviewer",
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            approve_submitted = st.form_submit_button(
                "✅ Approve",
                use_container_width=True,
                type="primary",
            )

        with col2:
            reject_submitted = st.form_submit_button(
                "❌ Reject",
                use_container_width=True,
            )

        with col3:
            edit_submitted = st.form_submit_button(
                "✏️ Request Edit",
                use_container_width=True,
            )

        edited_agent_1_result = None
        edited_agent_2_result = None
        if enable_editing:
            edited_agent_1_result = st.session_state.edited_agent_1
            edited_agent_2_result = st.session_state.edited_agent_2

        if approve_submitted:
            try:
                submitted = submit_human_review(
                    claim_id,
                    "approve",
                    feedback,
                    reviewed_by,
                    edited_agent_1_result=edited_agent_1_result,
                    edited_agent_2_result=edited_agent_2_result,
                )
            except requests.exceptions.RequestException as exc:
                st.session_state.error = f"Review submission error: {exc}"
                submitted = False

            if submitted:
                st.success("Claim approved! Resuming processing...")
                st.session_state.pending_review = False
                st.session_state.status_checking = True
                clear_review_edit_state()
                time.sleep(1)
                st.rerun()

        elif reject_submitted:
            try:
                submitted = submit_human_review(
                    claim_id,
                    "reject",
                    feedback,
                    reviewed_by,
                    edited_agent_1_result=edited_agent_1_result,
                    edited_agent_2_result=edited_agent_2_result,
                )
            except requests.exceptions.RequestException as exc:
                st.session_state.error = f"Review submission error: {exc}"
                submitted = False

            if submitted:
                st.error("Claim rejected. Resuming processing...")
                st.session_state.pending_review = False
                st.session_state.status_checking = True
                clear_review_edit_state()
                time.sleep(1)
                st.rerun()

        elif edit_submitted:
            if not feedback.strip():
                st.error("Please provide feedback when requesting edits")
            else:
                try:
                    submitted = submit_human_review(
                        claim_id,
                        "edit",
                        feedback,
                        reviewed_by,
                        edited_agent_1_result=edited_agent_1_result,
                        edited_agent_2_result=edited_agent_2_result,
                    )
                except requests.exceptions.RequestException as exc:
                    st.session_state.error = f"Review submission error: {exc}"
                    submitted = False

                if submitted:
                    st.info("Edit requested. Resuming processing...")
                    st.session_state.pending_review = False
                    st.session_state.status_checking = True
                    clear_review_edit_state()
                    time.sleep(1)
                    st.rerun()
