"""Tests for validate_diagnosis skill-based tool.

These tests verify that the diagnosis validation tool works correctly
with the new skill-based LangChain @tool architecture.
"""

import json

import pytest
from tools.skill_loader import load_agent_skills


def _get_validate_diagnosis_tool():
    """Get validate_diagnosis tool from loaded skills."""
    tools, _ = load_agent_skills("quality_agent")
    return next((t for t in tools if t.name == "validate-diagnosis"), None)


class TestValidateDiagnosisTool:
    """Tests for validate_diagnosis tool attributes."""

    def test_tool_name(self):
        """Tool should have the correct name."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None
        assert tool.name == "validate-diagnosis"

    def test_tool_has_description(self):
        """Tool should have a description."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None
        assert tool.description is not None
        assert len(tool.description) > 0


class TestValidateDiagnosisInvoke:
    """Tests for ICD-10 code validation via invoke()."""

    def test_tool_is_invokable(self):
        """Tool should be invokable."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None
        assert hasattr(tool, "invoke")

    def test_invoke_with_valid_input(self):
        """Should invoke successfully with valid input."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None

        result_str = tool.invoke({"diagnoses": ["Pneumonia"], "medications": ["Amoxicillin"]})
        result = json.loads(result_str)
        assert result["status_code"] == 0
        assert result["status_message"] == "success"

    def test_invoke_with_empty_diagnoses(self):
        """Should return error for empty diagnoses."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None

        result_str = tool.invoke({"diagnoses": [], "medications": ["Amoxicillin"]})
        result = json.loads(result_str)
        assert result["status_code"] == 2
        assert result["status_message"] == "error"

    def test_invoke_with_empty_medications(self):
        """Should return success with warning for empty medications."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None

        result_str = tool.invoke({"diagnoses": ["Pneumonia"], "medications": []})
        result = json.loads(result_str)
        assert result["status_code"] == 0
        assert "Không có thuốc" in result["data"]["message"]

    def test_invoke_returns_json_string(self):
        """Should return valid JSON string."""
        tool = _get_validate_diagnosis_tool()
        assert tool is not None

        result_str = tool.invoke({"diagnoses": ["Hypertension"], "medications": ["Amlodipine"]})
        assert isinstance(result_str, str)
        result = json.loads(result_str)
        assert "status_code" in result
        assert "status_message" in result
        assert "data" in result


class TestValidateDiagnosisIntegration:
    """Integration tests for skill loader and tool loading."""

    def test_quality_agent_loads_validate_diagnosis(self):
        """Quality agent should include validate_diagnosis tool."""
        tools, contexts = load_agent_skills("quality_agent")
        tool_names = [t.name for t in tools]
        assert "validate-diagnosis" in tool_names
        assert len(contexts) > 0

    def test_skill_context_contains_diagnosis_role(self):
        """Skill context should contain the diagnosis auditor role."""
        tools, contexts = load_agent_skills("quality_agent")
        assert "Medical Claim Quality Auditor" in contexts
        assert "validate-diagnosis" in contexts
