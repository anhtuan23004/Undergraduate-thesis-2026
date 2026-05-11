"""Pytest fixtures for agent-service tests."""

import pytest
from tools.skill_loader import load_agent_skills


@pytest.fixture
def skill_tools():
    """Fixture providing loaded skill-based tools."""
    return load_agent_skills("quality_agent")


@pytest.fixture
def check_required_documents_tool():
    """Fixture providing check_required_documents tool from skills."""
    tools, _ = load_agent_skills("completeness_agent")
    return next((t for t in tools if t.name == "check-required-docs"), None)


@pytest.fixture
def check_exclusion_tool():
    """Fixture providing check_exclusion tool from skills."""
    tools, _ = load_agent_skills("quality_agent")
    return next((t for t in tools if t.name == "check-exclusion"), None)
