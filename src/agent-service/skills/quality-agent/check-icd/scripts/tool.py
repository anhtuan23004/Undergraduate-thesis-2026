"""ICD lookup tool for diagnosis verification.

This tool wraps the existing lookup_icd function for use with the skill-based architecture.
"""

import json
import os
from urllib.parse import quote

import requests
from langchain_core.tools import tool

ICD10_BASE_URL = os.getenv("ICD10_BASE_URL", "https://ccs.whiteneuron.com/api/ICD10/search")


@tool("check-icd")
def check_icd(query: str) -> str:
    """Look up ICD entries by diagnosis text or ICD code and return JSON.

    This tool validates ICD-10 codes and retrieves official medical descriptions
    to verify that codes match their associated diagnoses.

    Args:
        query: Diagnosis text or ICD code to look up

    Returns:
        JSON string with lookup results
    """
    if not query or not query.strip():
        return json.dumps(
            {"status": "error", "message": "query is required", "results": []},
            ensure_ascii=False,
        )

    try:
        response = requests.get(
            f"{ICD10_BASE_URL}/{quote(query.strip(), safe='')}",
            params={"lang": "vi", "vol1": 1, "vol3": 0, "html": "true"},
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        return json.dumps(
            {"status": "error", "message": f"lookup failed: {exc}", "results": []},
            ensure_ascii=False,
        )

    try:
        payload = response.json()
        if isinstance(payload, dict):
            return json.dumps(
                {"status": "success", "query": query, "result": payload},
                ensure_ascii=False,
            )
    except Exception:  # nosec: B110 - Intentional fallback on JSON parse failure
        pass

    return json.dumps(
        {"status": "success", "query": query, "result": response.text},
        ensure_ascii=False,
    )


__all__ = ["check_icd"]
