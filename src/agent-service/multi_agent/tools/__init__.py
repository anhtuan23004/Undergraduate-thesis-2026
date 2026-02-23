"""Tool implementations for multi-agent system.

All tools follow the OpenAI function calling standard and inherit from BaseTool.
"""

from multi_agent.tools.base import BaseTool
from multi_agent.tools.extract_documents import ExtractDocumentsTool
from multi_agent.tools.classify_benefit import ClassifyBenefitTool
from multi_agent.tools.check_required_documents import CheckRequiredDocumentsTool
from multi_agent.tools.validate_consistency import ValidateConsistencyTool
from multi_agent.tools.validate_diagnosis import ValidateDiagnosisTool
from multi_agent.tools.check_exclusion import CheckExclusionTool
from multi_agent.tools.validate_medication import ValidateMedicationTool
from multi_agent.tools.aggregate_issues import AggregateIssuesTool

__all__ = [
    "BaseTool",
    "ExtractDocumentsTool",
    "ClassifyBenefitTool",
    "CheckRequiredDocumentsTool",
    "ValidateConsistencyTool",
    "ValidateDiagnosisTool",
    "CheckExclusionTool",
    "ValidateMedicationTool",
    "AggregateIssuesTool",
]