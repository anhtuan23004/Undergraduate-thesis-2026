"""Tests for agent skill discovery and tool mapping.

This test verifies that the skill loader correctly identifies and loads the 
appropriate tools for each agent based on the new architecture.
"""

import pytest
from tools.skill_loader import load_agent_skills

def test_completeness_agent_skills():
    """Verify CompletenessAgent loads its required tools."""
    tools, contexts = load_agent_skills("completeness_agent")
    tool_names = [t.name for t in tools]
    
    # Expected tools for Completeness Agent
    assert "classify-benefit" in tool_names
    assert "check-required-docs" in tool_names
    assert "validate-consistency" in tool_names
    
    # Context should contain administrative check instructions
    assert "Insurance Data Consistency Auditor" in contexts

def test_quality_agent_skills():
    """Verify QualityAgent loads its required tools."""
    tools, contexts = load_agent_skills("quality_agent")
    tool_names = [t.name for t in tools]
    
    # Expected tools for Quality Agent
    assert "check-icd" in tool_names
    assert "check-exclusion" in tool_names
    assert "validate-medication" in tool_names
    assert "search-medicine" in tool_names
    
    # Redundant tool should NOT be present (folder deleted)
    assert "validate-diagnosis" not in tool_names
    
    # Context should contain medical quality instructions
    assert "Medical Claim Quality Auditor" in contexts

def test_shared_skills_visibility():
    """Verify that shared skills are visible to all agents."""
    # classify-benefit is in skills/shared
    c_tools, _ = load_agent_skills("completeness_agent")
    q_tools, _ = load_agent_skills("quality_agent")
    
    assert "classify-benefit" in [t.name for t in c_tools]
    assert "classify-benefit" in [t.name for t in q_tools]
