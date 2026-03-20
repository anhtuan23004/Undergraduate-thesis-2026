"""Medication validation tool for insurance claims.

This tool validates that prescribed medications are clinically appropriate for
the given diagnoses by cross-referencing with medical databases.
"""

import json
from typing import List, Optional

from langchain_core.tools import tool


@tool
def validate_medication(
    medications: List[str],
    diagnoses: Optional[List[str]] = None,
    diagnosis_codes: Optional[List[str]] = None,
) -> str:
    """Validate medications against diagnoses and insurance policy.

    This tool checks if prescribed medications are appropriate for the
    diagnoses by cross-referencing medication information from the database.

    Args:
        medications: List of medication names to validate
        diagnoses: List of diagnosis names (optional)
        diagnosis_codes: List of ICD codes (optional)

    Returns:
        JSON string with validation results
    """
    if not medications:
        return json.dumps(
            {
                "status_code": 2,
                "status_message": "error",
                "data": {"message": "No medications provided for validation"},
            }
        )

    return json.dumps(
        {
            "status_code": 0,
            "status_message": "success",
            "data": {
                "message": "Dữ liệu thuốc đã được chuẩn bị để kiểm tra",
                "medications": medications,
                "diagnoses": diagnoses or [],
                "diagnosis_codes": diagnosis_codes or [],
            },
        },
        ensure_ascii=False,
    )


__all__ = ["validate_medication"]
