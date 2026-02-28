"""Streamlit UI for Agent Service - Insurance Claims Processing.

This module provides a comprehensive web interface for submitting and monitoring
insurance claim processing through the multi-agent workflow with human-in-the-loop support.

Features:
    - Claim submission with document upload
    - Real-time workflow visualization with polling
    - Human-in-the-loop review interface
    - Results dashboard with agent details
    - Error handling and validation
"""

import os
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8003")
API_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/process"
STATUS_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/status"
PENDING_REVIEWS_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/pending-reviews"
SUBMIT_REVIEW_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/submit-review"
HEALTH_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/health"

# Page configuration
st.set_page_config(
    page_title="Insurance Claims Processing",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Issue:
    """Represents an issue found during claim processing."""
    severity: str
    description: str
    field: Optional[str] = None


@dataclass
class AgentResult:
    """Represents the result from an agent's processing."""
    decision: str
    confidence: float
    reasoning: str
    missing_documents: Optional[List[str]] = None
    issues: Optional[List[Dict[str, Any]]] = None


@dataclass
class ProcessingStep:
    """Represents a step in the processing history."""
    step: str
    status: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None


# =============================================================================
# Session State Management
# =============================================================================

def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    defaults = {
        "claim_id": "",
        "policy_number": "",
        "uploaded_file": None,
        "processing": False,
        "result": None,
        "error": None,
        "current_step": "idle",
        "processing_history": [],
        "service_available": None,
        # New session state variables for human-in-the-loop
        "status_checking": False,
        "pending_review": False,
        "claim_status": None,
        "status_data": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_state() -> None:
    """Reset the session state to initial values."""
    st.session_state.claim_id = ""
    st.session_state.policy_number = ""
    st.session_state.uploaded_file = None
    st.session_state.processing = False
    st.session_state.result = None
    st.session_state.error = None
    st.session_state.current_step = "idle"
    st.session_state.processing_history = []
    st.session_state.status_checking = False
    st.session_state.pending_review = False
    st.session_state.claim_status = None
    st.session_state.status_data = None


def update_step(step: str, status: str = "in_progress", details: Optional[Dict] = None) -> None:
    """Update the current processing step and add to history.

    Args:
        step: The name of the current step
        status: The status of the step (pending, in_progress, completed, failed)
        details: Optional details about the step
    """
    st.session_state.current_step = step
    history_entry = {
        "step": step,
        "status": status,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "details": details or {}
    }
    st.session_state.processing_history.append(history_entry)


# =============================================================================
# API Client
# =============================================================================

def check_service_health() -> bool:
    """Check if the agent service is available.

    Returns:
        True if service is healthy, False otherwise
    """
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def submit_claim(claim_id: str, policy_number: str, file_path: str) -> Dict[str, Any]:
    """Submit a claim to the agent service for processing.

    Args:
        claim_id: Unique identifier for the claim
        policy_number: Policy number associated with the claim
        file_path: Path to the uploaded claim document

    Returns:
        Dictionary containing the processing result

    Raises:
        requests.exceptions.RequestException: If the API call fails
    """
    payload = {
        "claim_id": claim_id,
        "policy_number": policy_number,
        "input_file": file_path
    }

    response = requests.post(
        API_ENDPOINT,
        json=payload,
        timeout=30  # Shorter timeout for submission only
    )
    response.raise_for_status()
    return response.json()


def get_claim_status(claim_id: str) -> Optional[Dict[str, Any]]:
    """Get the current status of a claim.

    Args:
        claim_id: The claim ID to check

    Returns:
        Dictionary with status info or None if error
    """
    try:
        response = requests.get(
            f"{STATUS_ENDPOINT}/{claim_id}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        st.session_state.error = f"Status check error: {exc}"
        return None


def get_pending_reviews() -> List[Dict[str, Any]]:
    """Get list of claims waiting for human review.

    Returns:
        List of claim summaries pending review (unwrapped from PendingReviewsResponse)
    """
    try:
        response = requests.get(PENDING_REVIEWS_ENDPOINT, timeout=10)
        response.raise_for_status()
        data = response.json()
        # PendingReviewsResponse wraps the list: {"reviews": [...], "count": N}
        if isinstance(data, dict):
            return data.get("reviews", [])
        return data  # fallback if server returns a plain list
    except requests.exceptions.RequestException as exc:
        st.session_state.error = f"Pending reviews error: {exc}"
        return []


def submit_human_review(
    claim_id: str,
    decision: str,
    feedback: str,
    reviewed_by: str = "human",
    edited_agent_1_result: Optional[Dict[str, Any]] = None,
    edited_agent_2_result: Optional[Dict[str, Any]] = None
) -> bool:
    """Submit a human review decision for a claim.

    Args:
        claim_id: The claim ID being reviewed
        decision: The decision (approve, reject, edit)
        feedback: Feedback text
        reviewed_by: Name of reviewer
        edited_agent_1_result: Optional human-edited Agent 1 result
        edited_agent_2_result: Optional human-edited Agent 2 result

    Returns:
        True if submission successful, False otherwise
    """
    try:
        payload = {
            "decision": decision,
            "feedback": feedback,
            "reviewed_by": reviewed_by
        }
        # Include edited results if provided
        if edited_agent_1_result is not None:
            payload["edited_agent_1_result"] = edited_agent_1_result
        if edited_agent_2_result is not None:
            payload["edited_agent_2_result"] = edited_agent_2_result

        response = requests.post(
            f"{SUBMIT_REVIEW_ENDPOINT}/{claim_id}",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        st.session_state.error = f"Review submission error: {exc}"
        return False


# =============================================================================
# Polling Logic
# =============================================================================

def poll_claim_status() -> None:
    """Poll the claim status and update session state.

    This function checks the current status of the claim and updates
    the UI state accordingly. It handles transitions between:
    - starting/running: Continue polling
    - interrupted: Show human review interface
    - finished: Show final results
    - error: Show error message
    """
    claim_id = st.session_state.claim_id
    if not claim_id:
        return

    status_data = get_claim_status(claim_id)
    if status_data is None:
        return

    st.session_state.status_data = status_data
    status = status_data.get("status", "unknown")
    st.session_state.claim_status = status

    if status == "interrupted":
        # Claim needs human review
        st.session_state.status_checking = False
        st.session_state.pending_review = True
        st.session_state.current_step = "human_review"
        update_step("human_review", "in_progress", status_data)
    elif status == "finished":
        # Claim processing complete — store the entire ClaimStatusResponse as result
        st.session_state.status_checking = False
        st.session_state.pending_review = False
        st.session_state.result = status_data
        st.session_state.current_step = "completed"
        update_step("final_decision", "completed", status_data)
    elif status == "error":
        # Error occurred
        st.session_state.status_checking = False
        st.session_state.pending_review = False
        st.session_state.error = status_data.get("error", "Unknown error occurred")
        st.session_state.current_step = "error"
    else:
        # Still processing (starting or running)
        st.session_state.pending_review = False
        # Update current step based on which agent results are available
        if status_data.get("agent_2_result"):
            st.session_state.current_step = "quality_check"
        elif status_data.get("agent_1_result"):
            st.session_state.current_step = "completeness_check"
        else:
            st.session_state.current_step = "start"


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
        unsafe_allow_html=True
    )


def render_service_status() -> None:
    """Render the service availability status indicator."""
    if st.session_state.service_available is None:
        st.session_state.service_available = check_service_health()

    if st.session_state.service_available:
        st.sidebar.success("✅ Agent Service: Online")
    else:
        st.sidebar.error("❌ Agent Service: Offline")
        st.sidebar.info(f"Expected at: {AGENT_SERVICE_URL}")


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
                help="Unique identifier for this claim"
            )

        with col2:
            policy_number = st.text_input(
                "Policy Number *",
                value=st.session_state.policy_number,
                placeholder="e.g., POL-001",
                help="Policy number associated with this claim"
            )

        uploaded_file = st.file_uploader(
            "Upload Claim Document *",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Supported formats: PDF, PNG, JPG, JPEG"
        )

        submitted = st.form_submit_button(
            "🚀 Process Claim",
            use_container_width=True,
            type="primary"
        )

        if submitted:
            # Validate inputs
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
                # Save to session state and trigger processing
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

    # Define workflow steps
    steps = [
        ("completeness", "Completeness Check", "Agent 1 validates document completeness"),
        ("quality", "Quality Check", "Agent 2 validates quality and consistency"),
        ("human_review", "Human Review", "Human-in-the-loop for edge cases"),
        ("final_decision", "Final Decision", "Aggregate results and produce final output")
    ]

    # Determine current step index
    current_step_name = st.session_state.current_step
    step_mapping = {
        "idle": -1,
        "start": 0,
        "completeness_check": 0,
        "quality_check": 1,
        "human_review": 2,
        "final_decision": 3,
        "completed": 3,
        "error": -1
    }
    current_idx = step_mapping.get(current_step_name, -1)

    # Check if we're in interrupted state
    is_interrupted = st.session_state.claim_status == "interrupted"

    # Render workflow steps
    cols = st.columns(len(steps))
    for idx, (step_key, title, description) in enumerate(steps):
        with cols[idx]:
            if is_interrupted and step_key == "human_review":
                # Interrupted state - needs human attention
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
                    unsafe_allow_html=True
                )
            elif idx < current_idx:
                # Completed step
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
                    unsafe_allow_html=True
                )
            elif idx == current_idx:
                # Current step
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
                    unsafe_allow_html=True
                )
            else:
                # Pending step
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
                    unsafe_allow_html=True
                )

    # Add arrows between steps (except after last)
    if len(steps) > 1:
        arrow_cols = st.columns(len(steps) - 1)
        for i, col in enumerate(arrow_cols):
            with col:
                st.markdown(
                    """
                    <div style="text-align: center; font-size: 1.5rem; color: #6c757d; margin-top: -1rem;">
                        ➡️
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def render_polling_status() -> None:
    """Render the polling status while waiting for claim processing."""
    st.info("🔄 Processing claim... Please wait.")
    progress_bar = st.progress(0)

    # Calculate progress based on current step
    step_progress = {
        "start": 0.1,
        "completeness_check": 0.25,
        "quality_check": 0.50,
        "human_review": 0.75,
        "final_decision": 0.90,
        "completed": 1.0
    }
    progress = step_progress.get(st.session_state.current_step, 0.1)
    progress_bar.progress(progress)

    # Show current status details
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


def render_human_review_interface() -> None:
    """Render the human review interface for interrupted claims.

    This interface shows the agent results and allows the human reviewer
    to approve, reject, or request edits to the claim. It also allows
    direct editing of agent results before submission.
    """
    status_data = st.session_state.status_data or {}
    agent_results = status_data.get("agent_results", {})
    claim_id = st.session_state.claim_id

    st.header("👤 Human Review Required")

    # Warning banner
    st.warning(
        f"⚠️ Claim **{claim_id}** has been flagged for human review. "
        "Please review the agent findings below and provide your decision."
    )

    # Show agent results with editing capability
    st.subheader("Agent Findings (Editable)")

    # Initialize session state for edited results if not present
    if "edited_agent_1" not in st.session_state:
        agent1_original = agent_results.get("agent_1", {})
        st.session_state.edited_agent_1 = {
            "decision": agent1_original.get("decision", "accept"),
            "confidence": float(agent1_original.get("confidence", 0.8)),
            "reasoning": agent1_original.get("reasoning", ""),
            "issues": agent1_original.get("issues", [])
        }
    if "edited_agent_2" not in st.session_state:
        agent2_original = agent_results.get("agent_2", {})
        st.session_state.edited_agent_2 = {
            "decision": agent2_original.get("decision", "accept"),
            "confidence": float(agent2_original.get("confidence", 0.8)),
            "reasoning": agent2_original.get("reasoning", ""),
            "issues": agent2_original.get("issues", [])
        }
    if "enable_editing" not in st.session_state:
        st.session_state.enable_editing = False

    # Toggle for enabling editing
    enable_editing = st.checkbox(
        "✏️ Enable Editing of Agent Results",
        value=st.session_state.enable_editing,
        help="Check this to modify agent decisions, confidence, and reasoning before submission"
    )
    st.session_state.enable_editing = enable_editing

    col1, col2 = st.columns(2)

    with col1:
        with st.expander("📄 Agent 1: Completeness Check", expanded=True):
            agent1_data = agent_results.get("agent_1", {})
            if agent1_data:
                if enable_editing:
                    # Editable fields for Agent 1
                    st.markdown("**Edit Agent 1 Results:**")
                    st.session_state.edited_agent_1["decision"] = st.selectbox(
                        "Decision",
                        options=["accept", "reject", "accept_with_edit"],
                        index=["accept", "reject", "accept_with_edit"].index(
                            st.session_state.edited_agent_1.get("decision", "accept")
                        ),
                        key="agent1_decision"
                    )
                    st.session_state.edited_agent_1["confidence"] = st.slider(
                        "Confidence",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(st.session_state.edited_agent_1.get("confidence", 0.8)),
                        step=0.05,
                        key="agent1_confidence"
                    )
                    st.session_state.edited_agent_1["reasoning"] = st.text_area(
                        "Reasoning",
                        value=st.session_state.edited_agent_1.get("reasoning", ""),
                        height=80,
                        key="agent1_reasoning"
                    )

                    # Issues editor
                    st.markdown("**Issues:**")
                    issues_json = st.text_area(
                        "Issues (JSON format)",
                        value=str(st.session_state.edited_agent_1.get("issues", [])),
                        height=60,
                        key="agent1_issues"
                    )
                    try:
                        import json
                        st.session_state.edited_agent_1["issues"] = json.loads(issues_json.replace("'", '"'))
                    except json.JSONDecodeError:
                        st.session_state.edited_agent_1["issues"] = []

                    st.divider()
                    st.markdown("**Preview of Edited Result:**")

                # Display current values (original or edited)
                display_data = st.session_state.edited_agent_1 if enable_editing else agent1_data
                st.markdown(f"**Decision:** `{display_data.get('decision', 'N/A')}`")
                st.markdown(f"**Confidence:** {display_data.get('confidence', 0.0):.1%}")
                st.markdown(f"**Reasoning:** {display_data.get('reasoning', 'No reasoning provided')}")

                issues = display_data.get("issues", [])
                if issues:
                    st.markdown("**Issues Found:**")
                    for issue in issues:
                        severity = issue.get("severity", "medium") if isinstance(issue, dict) else "medium"
                        description = issue.get("description", str(issue)) if isinstance(issue, dict) else str(issue)
                        st.markdown(f"- **{str(severity).upper()}:** {description}")
            else:
                st.info("No completeness check data available")

    with col2:
        with st.expander("🔍 Agent 2: Quality Check", expanded=True):
            agent2_data = agent_results.get("agent_2", {})
            if agent2_data:
                if enable_editing:
                    # Editable fields for Agent 2
                    st.markdown("**Edit Agent 2 Results:**")
                    st.session_state.edited_agent_2["decision"] = st.selectbox(
                        "Decision",
                        options=["accept", "reject", "accept_with_edit"],
                        index=["accept", "reject", "accept_with_edit"].index(
                            st.session_state.edited_agent_2.get("decision", "accept")
                        ),
                        key="agent2_decision"
                    )
                    st.session_state.edited_agent_2["confidence"] = st.slider(
                        "Confidence",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(st.session_state.edited_agent_2.get("confidence", 0.8)),
                        step=0.05,
                        key="agent2_confidence"
                    )
                    st.session_state.edited_agent_2["reasoning"] = st.text_area(
                        "Reasoning",
                        value=st.session_state.edited_agent_2.get("reasoning", ""),
                        height=80,
                        key="agent2_reasoning"
                    )

                    # Issues editor
                    st.markdown("**Issues:**")
                    issues_json = st.text_area(
                        "Issues (JSON format)",
                        value=str(st.session_state.edited_agent_2.get("issues", [])),
                        height=60,
                        key="agent2_issues"
                    )
                    try:
                        import json
                        st.session_state.edited_agent_2["issues"] = json.loads(issues_json.replace("'", '"'))
                    except json.JSONDecodeError:
                        st.session_state.edited_agent_2["issues"] = []

                    st.divider()
                    st.markdown("**Preview of Edited Result:**")

                # Display current values (original or edited)
                display_data = st.session_state.edited_agent_2 if enable_editing else agent2_data
                st.markdown(f"**Decision:** `{display_data.get('decision', 'N/A')}`")
                st.markdown(f"**Confidence:** {display_data.get('confidence', 0.0):.1%}")
                st.markdown(f"**Reasoning:** {display_data.get('reasoning', 'No reasoning provided')}")

                issues = display_data.get("issues", [])
                if issues:
                    st.markdown("**Issues Found:**")
                    for issue in issues:
                        severity = issue.get("severity", "medium") if isinstance(issue, dict) else "medium"
                        description = issue.get("description", str(issue)) if isinstance(issue, dict) else str(issue)
                        st.markdown(f"- **{str(severity).upper()}:** {description}")
            else:
                st.info("No quality check data available")

    st.divider()

    # Review decision form
    st.subheader("Your Decision")

    with st.form("human_review_form"):
        feedback = st.text_area(
            "Feedback / Notes",
            placeholder="Enter your feedback, reasoning, or requested changes...",
            height=120,
            help="Your feedback will be recorded with your decision"
        )

        reviewed_by = st.text_input(
            "Reviewer Name",
            placeholder="Your name",
            value="Human Reviewer"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            approve_submitted = st.form_submit_button(
                "✅ Approve",
                use_container_width=True,
                type="primary"
            )

        with col2:
            reject_submitted = st.form_submit_button(
                "❌ Reject",
                use_container_width=True
            )

        with col3:
            edit_submitted = st.form_submit_button(
                "✏️ Request Edit",
                use_container_width=True
            )

        # Prepare edited results for submission if editing is enabled
        edited_agent_1_result = None
        edited_agent_2_result = None
        if enable_editing:
            edited_agent_1_result = st.session_state.edited_agent_1
            edited_agent_2_result = st.session_state.edited_agent_2

        # Handle form submission
        if approve_submitted:
            if submit_human_review(
                claim_id, "approve", feedback, reviewed_by,
                edited_agent_1_result=edited_agent_1_result,
                edited_agent_2_result=edited_agent_2_result
            ):
                st.success("Claim approved! Resuming processing...")
                st.session_state.pending_review = False
                st.session_state.status_checking = True
                # Clear edited results from session state
                for key in ["edited_agent_1", "edited_agent_2", "enable_editing"]:
                    if key in st.session_state:
                        del st.session_state[key]
                time.sleep(1)
                st.rerun()

        elif reject_submitted:
            if submit_human_review(
                claim_id, "reject", feedback, reviewed_by,
                edited_agent_1_result=edited_agent_1_result,
                edited_agent_2_result=edited_agent_2_result
            ):
                st.error("Claim rejected. Resuming processing...")
                st.session_state.pending_review = False
                st.session_state.status_checking = True
                # Clear edited results from session state
                for key in ["edited_agent_1", "edited_agent_2", "enable_editing"]:
                    if key in st.session_state:
                        del st.session_state[key]
                time.sleep(1)
                st.rerun()

        elif edit_submitted:
            if not feedback.strip():
                st.error("Please provide feedback when requesting edits")
            else:
                if submit_human_review(
                    claim_id, "edit", feedback, reviewed_by,
                    edited_agent_1_result=edited_agent_1_result,
                    edited_agent_2_result=edited_agent_2_result
                ):
                    st.info("Edit requested. Resuming processing...")
                    st.session_state.pending_review = False
                    st.session_state.status_checking = True
                    # Clear edited results from session state
                    for key in ["edited_agent_1", "edited_agent_2", "enable_editing"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    time.sleep(1)
                    st.rerun()


# =============================================================================
# Agent Result Normalizer
# =============================================================================

def _normalize_agent_result(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalise a raw agent result dict to the display schema.

    The agents (CompletenessAgent, QualityAgent) return a domain-specific dict
    that differs from the simplified AgentResult Pydantic model used for display.
    This function bridges the two.

    Args:
        raw: Raw dict from agent_1_result / agent_2_result / human_review_result

    Returns:
        Normalised dict with keys: decision, confidence, reasoning, issues,
        missing_documents
    """
    if not raw:
        return {}

    # ---- decision ----
    if "decision" in raw:
        decision = str(raw["decision"])
    elif "valid" in raw:
        decision = "accept" if raw["valid"] else "reject"
    else:
        decision = "unknown"

    # ---- confidence ----
    confidence = raw.get("confidence", 0.0)
    if isinstance(confidence, str):
        confidence = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(
            confidence.lower(), 0.5
        )
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    # ---- reasoning ----
    reasoning = raw.get("reasoning") or raw.get("reason", "")
    if not reasoning:
        # CompletenessAgent stores LLM output as a list of content blocks
        for block in raw.get("analysis", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                reasoning = block["text"]
                break

    # ---- issues ----
    issues: List[Dict[str, Any]] = []
    for issue in raw.get("issues", []) or []:
        if isinstance(issue, dict):
            issues.append({
                "severity": issue.get("severity", "medium"),
                # agents use "message", Pydantic model uses "description"
                "description": issue.get("description") or issue.get("message", ""),
                "field": issue.get("field", ""),
            })

    # ---- missing documents ----
    missing_docs = raw.get("missing_documents", []) or []
    # Also pull from document_check if present
    doc_check = raw.get("document_check") or {}
    if not missing_docs and doc_check:
        mandatory = doc_check.get("mandatory_documents", {}) or {}
        missing_docs = [
            m.get("name", m.get("type", str(m)))
            for m in mandatory.get("missing", []) or []
        ]

    return {
        "decision": decision,
        "confidence": confidence,
        "reasoning": reasoning,
        "issues": issues,
        "missing_documents": missing_docs,
    }


def get_decision_color(decision: str) -> str:
    """Get the color code for a decision.

    Args:
        decision: The final decision string

    Returns:
        CSS color code for the decision
    """
    decision_upper = decision.upper()
    if decision_upper == "APPROVE" or decision_upper == "ACCEPT":
        return "#28a745"  # Green
    elif decision_upper == "REJECT":
        return "#dc3545"  # Red
    elif decision_upper == "PENDING":
        return "#ffc107"  # Yellow
    else:
        return "#6c757d"  # Gray


def get_decision_emoji(decision: str) -> str:
    """Get the emoji for a decision.

    Args:
        decision: The final decision string

    Returns:
        Emoji representing the decision
    """
    decision_upper = decision.upper()
    if decision_upper == "APPROVE" or decision_upper == "ACCEPT":
        return "✅"
    elif decision_upper == "REJECT":
        return "❌"
    elif decision_upper == "PENDING":
        return "⏳"
    else:
        return "❓"


def render_agent_result_card(title: str, result: Dict[str, Any], icon: str) -> None:
    """Render a card displaying agent result details.

    Args:
        title: Title of the card
        result: Dictionary containing agent result data
        icon: Emoji icon for the card
    """
    if not result:
        st.info(f"{icon} {title}: No data available")
        return

    decision = result.get("decision", "N/A")
    confidence = result.get("confidence", 0.0)
    reasoning = result.get("reasoning", "No reasoning provided")
    issues = result.get("issues", [])
    missing_docs = result.get("missing_documents", [])

    # Determine card color based on decision
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
            unsafe_allow_html=True
        )

        st.markdown("**Reasoning:**")
        st.markdown(f"{reasoning}")

        # Display issues if any
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
                    "low": "#17a2b8"
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
                    unsafe_allow_html=True
                )

        # Display missing documents if any
        if missing_docs:
            st.markdown("**Missing Documents:**")
            for doc in missing_docs:
                st.markdown(f"- ❌ {doc}")


def render_results_dashboard() -> None:
    """Render the results dashboard with final decision and agent details."""
    if not st.session_state.result:
        return

    st.header("📊 Processing Results")

    # result is the full ClaimStatusResponse dict
    result = st.session_state.result
    claim_id = result.get("claim_id", st.session_state.claim_id or "Unknown")

    # Derive final decision from final_result or agent results
    final_result_raw = result.get("final_result") or {}
    final_decision = (
        final_result_raw.get("decision", "").upper()
        or final_result_raw.get("final_decision", "").upper()
    )
    if not final_decision:
        # Infer from agent results when explicit final_result absent
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

    # Final decision banner
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
        unsafe_allow_html=True
    )

    # Agent results — normalise raw agent dicts before rendering
    st.subheader("Agent Details")

    col1, col2 = st.columns(2)

    with col1:
        render_agent_result_card(
            "Agent 1: Completeness Check",
            _normalize_agent_result(result.get("agent_1_result")),
            "📄"
        )

    with col2:
        render_agent_result_card(
            "Agent 2: Quality Check",
            _normalize_agent_result(result.get("agent_2_result")),
            "🔍"
        )

    # Human review result if present
    human_review = result.get("human_review_result")
    if human_review:
        st.subheader("👤 Human Review")
        render_agent_result_card(
            "Human Review Result",
            _normalize_agent_result(human_review),
            "👤"
        )

    # Processing history timeline
    st.subheader("📜 Processing Timeline")
    # ClaimStatusResponse has no processing_steps; build a simple one from available data
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
                "failed": "❌"
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
                unsafe_allow_html=True
            )
    else:
        st.info("No processing history available")

    # Action buttons
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
                mime="application/json"
            )


def render_error_message() -> None:
    """Render error messages if any."""
    if st.session_state.error:
        st.error(f"❌ Error: {st.session_state.error}")


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
        help="Configure via AGENT_SERVICE_URL environment variable"
    )

    render_service_status()

    st.sidebar.divider()

    st.sidebar.subheader("📊 Statistics")
    st.sidebar.metric(
        label="Total Submissions",
        value=len(st.session_state.processing_history)
    )

    # Show pending reviews section if service is available
    if st.session_state.service_available:
        st.sidebar.divider()
        st.sidebar.subheader("⏳ Pending Reviews")
        if st.sidebar.button("Refresh Pending List"):
            pending = get_pending_reviews()
            if pending:
                for item in pending:
                    # get_pending_reviews() now always returns a list of dicts
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


# =============================================================================
# Main Application Logic
# =============================================================================

def start_claim_processing() -> None:
    """Start the claim processing by submitting to the backend.

    This function saves the uploaded file and submits the claim,
    then starts the polling mechanism.
    """
    try:
        # Update to start step
        update_step("start", "in_progress")

        # Save uploaded file to the UPLOADS_DIR that the API expects
        uploaded_file = st.session_state.uploaded_file
        if uploaded_file is not None:
            # Must match UPLOADS_DIR env var used by MultiAgentRequest validator
            uploads_dir = os.getenv("UPLOADS_DIR", "/tmp/agent-service/uploads")
            os.makedirs(uploads_dir, exist_ok=True)

            # Save file and keep only the filename to send as relative path
            file_name = uploaded_file.name
            file_path = os.path.join(uploads_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
        else:
            raise ValueError("No file uploaded")

        # Submit claim — send only filename, not absolute path
        result = submit_claim(
            claim_id=st.session_state.claim_id,
            policy_number=st.session_state.policy_number,
            file_path=file_name
        )

        # Start polling for status
        st.session_state.processing = False
        st.session_state.status_checking = True
        st.session_state.error = None

        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)

    except requests.exceptions.ConnectionError:
        st.session_state.error = "Cannot connect to agent service. Please ensure it's running."
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
        st.session_state.service_available = False
    except requests.exceptions.Timeout:
        st.session_state.error = "Request timed out. The service may be busy."
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
    except requests.exceptions.HTTPError as e:
        st.session_state.error = f"API Error: {e.response.status_code} - {e.response.text}"
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"
    except Exception as e:
        st.session_state.error = f"Unexpected error: {str(e)}"
        st.session_state.processing = False
        st.session_state.status_checking = False
        st.session_state.current_step = "error"


def main() -> None:
    """Main application entry point."""
    # Initialize session state
    init_session_state()

    # Render sidebar
    render_sidebar()

    # Render main content
    render_header()

    # Show error messages
    render_error_message()

    # Render workflow visualization
    render_workflow_visualization()

    # Determine which UI state to show
    if st.session_state.processing:
        # Initial submission in progress
        render_polling_status()
        start_claim_processing()
        st.rerun()

    elif st.session_state.status_checking:
        # Polling for status
        poll_claim_status()
        current_status = st.session_state.claim_status

        if current_status == "interrupted":
            # Show human review interface
            render_human_review_interface()
        elif current_status == "finished":
            # Show final results
            render_results_dashboard()
        elif current_status == "error":
            # Show error
            st.error("Processing failed. Please check the error message above.")
            if st.button("🔄 Try Again"):
                reset_state()
                st.rerun()
        else:
            # Still processing - show polling status and auto-refresh
            render_polling_status()
            time.sleep(2)
            st.rerun()

    elif st.session_state.pending_review:
        # Show human review interface
        render_human_review_interface()

    elif st.session_state.result:
        # Show final results
        render_results_dashboard()

    else:
        # Show claim submission form
        render_claim_submission_form()


if __name__ == "__main__":
    main()
