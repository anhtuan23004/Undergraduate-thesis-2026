"""Document consistency validation tool.

This tool validates consistency of information across multiple documents
in an insurance claim file.
"""

import json
from typing import Dict, List, Optional

from langchain_core.tools import tool


@tool("validate-consistency")
def validate_consistency(documents: List[Dict], treatment_type: Optional[str] = None) -> str:
    """Validate consistency of key information across multiple documents.

    This tool checks that the insured person's name is consistent across
    all documents and that treatment dates are logically consistent.

    Args:
        documents: List of document data (each as a dict)
        treatment_type: Treatment type ("Ngoại trú" or "Nội trú")

    Returns:
        JSON string with consistency validation result
    """
    if not documents:
        return json.dumps({"error": "No documents provided for validation"})

    # This tool provides input data for the LLM to process
    # The actual validation logic is performed by the LLM using the skill context
    return json.dumps(
        {
            "documents": documents,
            "treatment_type": treatment_type,
        },
        ensure_ascii=False,
    )


__all__ = ["validate_consistency"]
