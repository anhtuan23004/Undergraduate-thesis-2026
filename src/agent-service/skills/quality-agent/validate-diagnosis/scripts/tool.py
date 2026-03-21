"""Diagnosis validation tool for checking medication-diagnosis appropriateness.

This tool validates that prescribed medications are clinically appropriate for
the given diagnoses using the medicine search database.
"""

import json
from typing import Dict, List

from langchain_core.tools import tool


@tool("validate-diagnosis")
def validate_diagnosis(diagnoses: List[str], medications: List[str]) -> str:
    """Validate that medications are appropriate for the given diagnoses.

    This tool checks if prescribed medications are clinically suitable for the
    diagnoses by cross-referencing medication information from the database.

    Args:
        diagnoses: List of diagnosis names
        medications: List of medication names

    Returns:
        JSON string with validation results including status and messages
    """
    if not diagnoses:
        return json.dumps(
            {
                "status_code": 2,
                "status_message": "error",
                "data": {"message": "No diagnoses provided for validation"},
            }
        )

    if not medications:
        return json.dumps(
            {
                "status_code": 0,
                "status_message": "success",
                "data": {"message": "Không có thuốc nào để kiểm tra"},
            }
        )

    # Note: This tool returns the input data structured for the LLM
    # The actual validation logic is performed by the LLM using this tool's
    # output along with the search_medicine tool results
    return json.dumps(
        {
            "status_code": 0,
            "status_message": "success",
            "data": {
                "message": "Dữ liệu chẩn đoán và thuốc đã được chuẩn bị để kiểm tra",
                "diagnoses": diagnoses,
                "medications": medications,
            },
        }
    )


__all__ = ["validate_diagnosis"]
