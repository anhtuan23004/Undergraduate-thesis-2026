"""Unit tests for Streamlit result normalization helpers."""

from interfaces.web.result_utils import normalize_agent_result, normalize_run_output


class TestNormalizeAgentResult:
    """Validate normalization adapter used by v2 UI."""

    def test_normalize_with_valid_flag(self):
        """Map legacy valid flag to decision field."""
        normalized = normalize_agent_result(
            {
                "valid": True,
                "confidence": "high",
                "issues": [],
            }
        )

        assert normalized["decision"] == "accept"
        assert normalized["confidence"] == 0.9

    def test_normalize_issues_description_from_message(self):
        """Support issue blocks that use 'message' instead of 'description'."""
        normalized = normalize_agent_result(
            {
                "decision": "reject",
                "issues": [
                    {"severity": "high", "message": "Missing field", "field": "documents"}
                ],
            }
        )

        assert normalized["decision"] == "reject"
        assert normalized["issues"][0]["description"] == "Missing field"
        assert normalized["issues"][0]["field"] == "documents"

    def test_normalize_missing_documents_from_document_check(self):
        """Backfill missing documents from document_check payload."""
        normalized = normalize_agent_result(
            {
                "decision": "accept_with_edit",
                "document_check": {
                    "mandatory_documents": {
                        "missing": [{"name": "invoice"}, {"type": "lab_result"}]
                    }
                },
            }
        )

        assert normalized["missing_documents"] == ["invoice", "lab_result"]


class TestNormalizeRunOutput:
    """Validate run-level output adapter."""

    def test_prefers_final_output_for_v2(self):
        """Use final_output as canonical result when present."""
        normalized = normalize_run_output(
            {
                "run_id": "run_1",
                "final_output": {"decision": "APPROVE"},
                "final_result": {"decision": "REJECT"},
            }
        )

        assert normalized["final_result"]["decision"] == "APPROVE"
        assert normalized["final_output"]["decision"] == "APPROVE"

    def test_fallback_to_final_result(self):
        """Fallback to legacy final_result when final_output absent."""
        normalized = normalize_run_output(
            {
                "run_id": "run_1",
                "final_result": {"decision": "REJECT"},
            }
        )

        assert normalized["final_output"]["decision"] == "REJECT"
