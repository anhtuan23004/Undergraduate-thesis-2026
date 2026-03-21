"""Exclusion check tool for validating diagnosis against policy exclusions.

This tool checks if diagnoses fall under excluded categories (congenital, mental,
STDs, occupational diseases) according to insurance policy.
"""

import json
from typing import List

from langchain_core.tools import tool


@tool("check-exclusion")
def check_exclusion(diagnoses: List[str]) -> str:
    """Check if diagnoses are excluded from insurance coverage.

    This tool validates diagnoses against policy exclusion criteria to determine
    coverage eligibility.

    Args:
        diagnoses: List of diagnosis names or ICD codes

    Returns:
        JSON string with exclusion check results
    """
    if not diagnoses:
        return json.dumps(
            {
                "status_code": 2,
                "status_message": "error",
                "data": {"message": "No diagnoses provided for exclusion check"},
            }
        )

    # Note: This tool returns the input data structured for the LLM
    # The actual exclusion check logic is performed by the LLM using
    # this tool's output
    return json.dumps(
        {
            "status_code": 0,
            "status_message": "success",
            "data": {
                "message": "Dữ liệu chẩn đoán đã được chuẩn bị để kiểm tra điều khoản loại trừ",
                "diagnoses": diagnoses,
            },
        }
    )


__all__ = ["check_exclusion"]
