"""Streamlit UI for Agent Service - Insurance Claims Processing."""

import time

import streamlit as st

from processing import poll_claim_status, start_claim_processing
from render_human_review import render_human_review_interface
from render_results import render_results_dashboard
from render_sidebar import render_sidebar
from state import init_session_state, reset_state

st.set_page_config(
    page_title="Insurance Claims Processing",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# UI Components
# =============================================================================


def render_header() -> None:
    """Render the application header with title and description."""
    st.title("🏥 Insurance Claims Processing")
    st.markdown(
        """
        <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
            <h4 style="margin: 0; color: #1f1f1f;">Multi-Agent AI System with Human-in-the-Loop</h4>
            <p style="margin: 0.5rem 0 0 0; color: #555;">
                Submit insurance claims for automated processing through our intelligent multi-agent workflow.
                The system performs completeness checks, quality validation, and includes human review for edge cases.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_claim_submission_form() -> None:
    """Render the claim submission form with input validation."""
    st.header("📋 Submit New Claim")

    with st.form("claim_submission_form"):
        col1, col2 = st.columns(2)

        with col1:
            claim_id = st.text_input(
                "Claim ID *",
                value=st.session_state.claim_id,
                placeholder="e.g., CLM-2024-001",
                help="Unique identifier for this claim",
            )

        with col2:
            policy_number = st.text_input(
                "Policy Number *",
                value=st.session_state.policy_number,
                placeholder="e.g., POL-001",
                help="Policy number associated with this claim",
            )

        uploaded_file = st.file_uploader(
            "Upload Claim Document *",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Supported formats: PDF, PNG, JPG, JPEG",
        )

        submitted = st.form_submit_button(
            "🚀 Process Claim",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            errors = []
            if not claim_id or not claim_id.strip():
                errors.append("Claim ID is required")
            if not policy_number or not policy_number.strip():
                errors.append("Policy number is required")
            if not uploaded_file:
                errors.append("Please upload a claim document")

            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                st.session_state.claim_id = claim_id.strip()
                st.session_state.policy_number = policy_number.strip()
                st.session_state.uploaded_file = uploaded_file
                st.session_state.processing = True
                st.session_state.error = None
                st.session_state.result = None
                st.session_state.processing_history = []
                st.session_state.status_checking = False
                st.session_state.pending_review = False
                st.rerun()


def render_workflow_visualization() -> None:
    """Render the visual workflow diagram with status indicators."""
    st.header("🔄 Processing Workflow")

    steps = [
        ("completeness", "Completeness Check", "Agent 1 validates document completeness"),
        ("quality", "Quality Check", "Agent 2 validates quality and consistency"),
        ("human_review", "Human Review", "Human-in-the-loop for edge cases"),
        ("final_decision", "Final Decision", "Aggregate results and produce final output"),
    ]

    current_step_name = st.session_state.current_step
    step_mapping = {
        "idle": -1,
        "start": 0,
        "completeness_check": 0,
        "quality_check": 1,
        "human_review": 2,
        "final_decision": 3,
        "completed": 3,
        "error": -1,
    }
    current_idx = step_mapping.get(current_step_name, -1)

    is_interrupted = st.session_state.claim_status == "interrupted"

    cols = st.columns(len(steps))
    for idx, (step_key, title, description) in enumerate(steps):
        with cols[idx]:
            if is_interrupted and step_key == "human_review":
                st.markdown(
                    f"""
                    <div style="
                        background-color: #fff3cd;
                        border: 3px solid #fd7e14;
                        border-radius: 10px;
                        padding: 1rem;
                        text-align: center;
                        animation: pulse-orange 2s infinite;
                    ">
                        <div style="font-size: 2rem;">👤</div>
                        <div style="font-weight: bold; color: #856404;">{title}</div>
                        <div style="font-size: 0.8rem; color: #856404;">⚠️ Action Required</div>
                    </div>
                    <style>
                        @keyframes pulse-orange {{
                            0% {{ box-shadow: 0 0 0 0 rgba(253, 126, 20, 0.7); }}
                            70% {{ box-shadow: 0 0 0 10px rgba(253, 126, 20, 0); }}
                            100% {{ box-shadow: 0 0 0 0 rgba(253, 126, 20, 0); }}
                        }}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
            elif idx < current_idx:
                st.markdown(
                    f"""
                    <div style="
                        background-color: #d4edda;
                        border: 2px solid #28a745;
                        border-radius: 10px;
                        padding: 1rem;
                        text-align: center;
                    ">
                        <div style="font-size: 2rem;">✅</div>
                        <div style="font-weight: bold; color: #155724;">{title}</div>
                        <div style="font-size: 0.8rem; color: #155724;">{description}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif idx == current_idx:
                st.markdown(
                    f"""
                    <div style="
                        background-color: #fff3cd;
                        border: 2px solid #ffc107;
                        border-radius: 10px;
                        padding: 1rem;
                        text-align: center;
                        animation: pulse 2s infinite;
                    ">
                        <div style="font-size: 2rem;">⏳</div>
                        <div style="font-weight: bold; color: #856404;">{title}</div>
                        <div style="font-size: 0.8rem; color: #856404;">{description}</div>
                    </div>
                    <style>
                        @keyframes pulse {{
                            0% {{ box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7); }}
                            70% {{ box-shadow: 0 0 0 10px rgba(255, 193, 7, 0); }}
                            100% {{ box-shadow: 0 0 0 0 rgba(255, 193, 7, 0); }}
                        }}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="
                        background-color: #f8f9fa;
                        border: 2px solid #dee2e6;
                        border-radius: 10px;
                        padding: 1rem;
                        text-align: center;
                        opacity: 0.6;
                    ">
                        <div style="font-size: 2rem; color: #6c757d;">⏸️</div>
                        <div style="font-weight: bold; color: #6c757d;">{title}</div>
                        <div style="font-size: 0.8rem; color: #6c757d;">{description}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    if len(steps) > 1:
        arrow_cols = st.columns(len(steps) - 1)
        for _, col in enumerate(arrow_cols):
            with col:
                st.markdown(
                    """
                    <div style="text-align: center; font-size: 1.5rem; color: #6c757d; margin-top: -1rem;">
                        ➡️
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_polling_status() -> None:
    """Render the polling status while waiting for claim processing."""
    st.info("🔄 Processing claim... Please wait.")
    progress_bar = st.progress(0)

    step_progress = {
        "start": 0.1,
        "completeness_check": 0.25,
        "quality_check": 0.50,
        "human_review": 0.75,
        "final_decision": 0.90,
        "completed": 1.0,
    }
    progress = step_progress.get(st.session_state.current_step, 0.1)
    progress_bar.progress(progress)

    status_data = st.session_state.status_data or {}

    st.caption("Agent progress:")
    cols = st.columns(2)
    with cols[0]:
        if status_data.get("agent_1_result"):
            st.success("✅ Completeness Check completed")
        else:
            st.info("⏳ Completeness Check in progress...")
    with cols[1]:
        if status_data.get("agent_2_result"):
            st.success("✅ Quality Check completed")
        elif status_data.get("agent_1_result"):
            st.info("⏳ Quality Check in progress...")
        else:
            st.info("⏸️ Quality Check pending")

    st.caption(f"Claim ID: `{st.session_state.claim_id}`")


def render_error_message() -> None:
    """Render error messages if any."""
    if st.session_state.error:
        st.error(f"❌ Error: {st.session_state.error}")


# =============================================================================
# Main Application Logic
# =============================================================================


def main() -> None:
    """Main application entry point."""
    init_session_state()

    render_sidebar()
    render_header()
    render_error_message()
    render_workflow_visualization()

    if st.session_state.processing:
        render_polling_status()
        start_claim_processing()
        st.rerun()

    elif st.session_state.status_checking:
        poll_claim_status()
        current_status = st.session_state.claim_status

        if current_status == "interrupted":
            render_human_review_interface()
        elif current_status == "finished":
            render_results_dashboard()
        elif current_status == "error":
            st.error("Processing failed. Please check the error message above.")
            if st.button("🔄 Try Again"):
                reset_state()
                st.rerun()
        else:
            render_polling_status()
            time.sleep(2)
            st.rerun()

    elif st.session_state.pending_review:
        render_human_review_interface()

    elif st.session_state.result:
        render_results_dashboard()

    else:
        render_claim_submission_form()


if __name__ == "__main__":
    main()
