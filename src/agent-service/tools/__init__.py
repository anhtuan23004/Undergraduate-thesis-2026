"""Tool implementations for multi-agent system.

All tools follow the OpenAI function calling standard and inherit from BaseTool.
"""

from tools.base import BaseTool
from tools.extract_documents import ExtractDocumentsTool
from tools.classify_benefit import ClassifyBenefitTool
from tools.check_required_documents import CheckRequiredDocumentsTool
from tools.validate_consistency import ValidateConsistencyTool
from tools.validate_diagnosis import ValidateDiagnosisTool
from tools.check_exclusion import CheckExclusionTool
from tools.validate_medication import ValidateMedicationTool
from tools.aggregate_issues import AggregateIssuesTool

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