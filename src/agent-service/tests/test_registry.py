"""Tests for skill-based tool loading functionality.

These tests verify that tools are correctly discovered and loaded
using the skill-based architecture.
"""

import pytest
from tools.skill_loader import load_agent_skills, clear_skill_cache


class TestSkillLoaderDiscovery:
    """Tests for skill loader discovery mechanism."""

    def test_load_quality_agent_skills(self):
        """Should load quality agent skills."""
        tools, contexts = load_agent_skills("quality_agent")
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "check_icd" in tool_names
        assert "validate_diagnosis" in tool_names
        assert len(contexts) > 0

    def test_load_completeness_agent_skills(self):
        """Should load completeness agent skills."""
        tools, contexts = load_agent_skills("completeness_agent")
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "extract_documents" in tool_names
        assert "check_required_documents" in tool_names
        assert len(contexts) > 0

    def test_load_decision_agent_skills(self):
        """Should load decision agent skills."""
        tools, contexts = load_agent_skills("decision_agent")
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "aggregate_issues" in tool_names
        assert len(contexts) > 0

    def test_load_nonexistent_agent(self):
        """Should handle nonexistent agent gracefully but still load shared tools."""
        tools, contexts = load_agent_skills("nonexistent_agent")
        tool_names = [t.name for t in tools]
        assert "classify_benefit" in tool_names
        assert "classify-benefit" in contexts


class TestSkillLoaderCaching:
    """Tests for skill loader caching mechanism."""

    def test_skills_are_cached(self):
        """Loaded skills should be cached."""
        clear_skill_cache()
        tools1, _ = load_agent_skills("quality_agent")
        tools2, _ = load_agent_skills("quality_agent")
        assert tools1 == tools2

    def test_cache_can_be_cleared(self):
        """Cache can be cleared."""
        clear_skill_cache()
        tools, _ = load_agent_skills("quality_agent")
        clear_skill_cache()
        tools2, _ = load_agent_skills("quality_agent")
        assert len(tools) > 0
        assert len(tools2) > 0


class TestSkillContextInjection:
    """Tests for skill context injection."""

    def test_skill_contexts_contain_role(self):
        """Skill contexts should contain role information."""
        tools, contexts = load_agent_skills("quality_agent")
        assert len(contexts) > 0
        assert "Medical Claim Quality Auditor" in contexts

    def test_skill_contexts_contain_tool_name(self):
        """Skill contexts should contain tool names as headings."""
        tools, contexts = load_agent_skills("quality_agent")
        assert len(contexts) > 0
        assert "### Available Tool:" in contexts
        assert "check-icd" in contexts


class TestSharedSkills:
    """Tests for shared skills loading."""

    def test_shared_skills_loaded_with_agent(self):
        """Shared skills should be loaded with agent skills."""
        tools, contexts = load_agent_skills("quality_agent")
        tool_names = [t.name for t in tools]
        assert "classify_benefit" in tool_names

    def test_completeness_agent_includes_shared(self):
        """Completeness agent should include shared skills."""
        tools, contexts = load_agent_skills("completeness_agent")
        tool_names = [t.name for t in tools]
        assert "classify_benefit" in tool_names
