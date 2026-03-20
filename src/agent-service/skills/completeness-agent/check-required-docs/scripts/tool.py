"""Required documents check tool.

This tool validates that all required documents are present based on
benefit type and treatment type according to insurance policy rules.
"""

import json
from typing import Dict, List

from langchain_core.tools import tool


@tool
def check_required_documents(
    benefit_type: str,
    treatment_type: str,
    submitted_documents: List[str]
) -> str:
    """Check if required documents are present for the given benefit and treatment types.

    This tool verifies document completeness according to insurance policy rules.

    Args:
        benefit_type: Type of insurance benefit (e.g., "Tai nạn", "Ốm bệnh", "Răng")
        treatment_type: Type of treatment ("Nội trú" or "Ngoại trú")
        submitted_documents: List of document names submitted

    Returns:
        JSON string with completeness check result
    """
    if not benefit_type or not treatment_type:
        return json.dumps({
            "error": "benefit_type and treatment_type are required"
        })

    if not submitted_documents:
        submitted_documents = []

    # This tool provides input data for the LLM to process
    # The actual validation logic is performed by the LLM using the skill context
    return json.dumps({
        "benefit_type": benefit_type,
        "treatment_type": treatment_type,
        "submitted_documents": submitted_documents,
    }, ensure_ascii=False)


__all__ = ["check_required_documents"]
