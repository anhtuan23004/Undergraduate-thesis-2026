"""HTTP client helpers for agent-service APIs used by Streamlit UI."""

from typing import Any, Dict, List, Optional

import requests

from constants import (
    API_ENDPOINT,
    HEALTH_ENDPOINT,
    PENDING_REVIEWS_ENDPOINT,
    STATUS_ENDPOINT,
    SUBMIT_REVIEW_ENDPOINT,
)


def check_service_health() -> bool:
    """Check if the agent service is available."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def submit_claim(claim_id: str, policy_number: str, file_path: str) -> Dict[str, Any]:
    """Submit a claim to the agent service for background processing."""
    payload = {
        "claim_id": claim_id,
        "policy_number": policy_number,
        "input_file": file_path,
    }

    response = requests.post(
        API_ENDPOINT,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_claim_status(claim_id: str) -> Optional[Dict[str, Any]]:
    """Get the current status of a claim."""
    response = requests.get(
        f"{STATUS_ENDPOINT}/{claim_id}",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_pending_reviews() -> List[Dict[str, Any]]:
    """Get list of claims waiting for human review."""
    response = requests.get(PENDING_REVIEWS_ENDPOINT, timeout=10)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        return data.get("reviews", [])
    return data


def submit_human_review(
    claim_id: str,
    decision: str,
    feedback: str,
    reviewed_by: str = "human",
    edited_agent_1_result: Optional[Dict[str, Any]] = None,
    edited_agent_2_result: Optional[Dict[str, Any]] = None,
) -> bool:
    """Submit a human review decision for a claim."""
    payload = {
        "decision": decision,
        "feedback": feedback,
        "reviewed_by": reviewed_by,
    }
    if edited_agent_1_result is not None:
        payload["edited_agent_1_result"] = edited_agent_1_result
    if edited_agent_2_result is not None:
        payload["edited_agent_2_result"] = edited_agent_2_result

    response = requests.post(
        f"{SUBMIT_REVIEW_ENDPOINT}/{claim_id}",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return True
