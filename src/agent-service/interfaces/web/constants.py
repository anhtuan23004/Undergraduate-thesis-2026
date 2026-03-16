"""Configuration constants for the Streamlit web interface."""

import os

from dotenv import load_dotenv

load_dotenv()

AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8003")
API_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/process"
STATUS_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/status"
PENDING_REVIEWS_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/pending-reviews"
SUBMIT_REVIEW_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/submit-review"
HEALTH_ENDPOINT = f"{AGENT_SERVICE_URL}/api/v1/multi-agent/health"
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/tmp/agent-service/uploads")
