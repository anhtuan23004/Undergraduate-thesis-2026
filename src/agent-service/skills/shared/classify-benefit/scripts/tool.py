"""Benefit classification tool for insurance claims.

This tool classifies the insurance benefit type based on document content
and claim information.
"""

import json
from typing import List, Optional

from langchain_core.tools import tool


@tool("classify-benefit")
def classify_benefit(
    diagnosis: Optional[str] = None, treatment: Optional[str] = None, documents: Optional[List[str]] = None
) -> str:
    """Classify the insurance benefit type from claim information.

    This tool determines whether the claim is for:
    - Tai nạn (Accident)
    - Ốm bệnh (Illness)
    - Thai sản (Maternity)
    - Răng (Dental)

    Args:
        diagnosis: Primary diagnosis text
        treatment: Type of treatment received
        documents: List of document types present

    Returns:
        JSON string with classification result
    """
    # This tool provides input data for the LLM to classify
    # The actual classification logic is performed by the LLM using the skill context
    return json.dumps(
        {
            "diagnosis": diagnosis,
            "treatment": treatment,
            "documents": documents or [],
        },
        ensure_ascii=False,
    )


__all__ = ["classify_benefit"]
