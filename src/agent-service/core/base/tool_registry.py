"""Tool Registry for skill-based agent architecture.

Maps tool names (as declared in config/agents/*.yaml) to their
implementation classes. This allows SkillAgent to instantiate the
correct tools from YAML config at runtime.
"""

from features.completeness.tools.extract_documents import ExtractDocumentsTool
from features.completeness.tools.classify_benefit import ClassifyBenefitTool
from features.completeness.tools.check_required_documents import CheckRequiredDocumentsTool
from features.quality.tools.validate_consistency import ValidateConsistencyTool
from features.quality.tools.validate_diagnosis import ValidateDiagnosisTool
from features.quality.tools.check_exclusion import CheckExclusionTool
from features.quality.tools.validate_medication import ValidateMedicationTool
from features.decision.tools.aggregate_issues import AggregateIssuesTool

TOOL_REGISTRY: dict = {
    "extract_documents": ExtractDocumentsTool,
    "classify_benefit": ClassifyBenefitTool,
    "check_required_documents": CheckRequiredDocumentsTool,
    "validate_consistency": ValidateConsistencyTool,
    "validate_diagnosis": ValidateDiagnosisTool,
    "check_exclusion": CheckExclusionTool,
    "validate_medication": ValidateMedicationTool,
    "aggregate_issues": AggregateIssuesTool,
}
