"""ICD lookup tool for diagnosis verification.

This tool wraps the existing lookup_icd function for use with the skill-based architecture.
"""

import json
import os
import re
from urllib.parse import quote

import requests
from langchain_core.tools import tool

ICD10_BASE_URL = os.getenv("ICD10_BASE_URL", "https://ccs.whiteneuron.com/api/ICD10/search")
ICD_REFERENCE_BASE_URL = "https://icd.kcb.vn/icd-10/icd10"
ICD_CODE_PATTERN = re.compile(r"\b[A-Z][0-9]{2}(?:\.?[0-9A-Z]{1,4})?\b", re.IGNORECASE)


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
                _build_success_response(query, payload),
                ensure_ascii=False,
            )
    except Exception:  # nosec: B110 - Intentional fallback on JSON parse failure
        pass

    return json.dumps(
        _build_success_response(query, response.text),
        ensure_ascii=False,
    )


def _build_success_response(query: str, result: object) -> dict:
    """Build a backward-compatible response enriched with deterministic ICD links."""
    enriched_result = _add_reference_urls(result)
    codes = sorted(set(_extract_icd_codes(query)) | set(_extract_icd_codes(enriched_result)))
    response = {
        "status": "success",
        "query": query,
        "result": enriched_result,
    }
    if codes:
        reference_urls = {code: _icd_reference_url(code) for code in codes}
        response["reference_urls"] = reference_urls
        if len(codes) == 1:
            response["reference_url"] = reference_urls[codes[0]]
    return response


def _add_reference_urls(value: object) -> object:
    """Recursively add reference_url beside ICD-like code fields."""
    if isinstance(value, list):
        return [_add_reference_urls(item) for item in value]

    if not isinstance(value, dict):
        return value

    enriched = {key: _add_reference_urls(item) for key, item in value.items()}
    if "reference_url" in enriched:
        return enriched

    codes: list[str] = []
    for key, item in value.items():
        if isinstance(item, str) and _is_icd_code_key(key):
            codes.extend(_extract_icd_codes(item))

    unique_codes = sorted(set(codes))
    if len(unique_codes) == 1:
        enriched["reference_url"] = _icd_reference_url(unique_codes[0])

    return enriched


def _is_icd_code_key(key: str) -> bool:
    """Return whether a response key is likely to contain an ICD code."""
    normalized = key.lower()
    return "icd" in normalized or normalized in {"code", "diagnosis_code"}


def _extract_icd_codes(value: object) -> list[str]:
    """Extract normalized ICD-like codes from selected strings and containers."""
    if isinstance(value, str):
        return [_normalize_icd_code(match.group(0)) for match in ICD_CODE_PATTERN.finditer(value)]

    if isinstance(value, list):
        codes: list[str] = []
        for item in value:
            codes.extend(_extract_icd_codes(item))
        return codes

    if isinstance(value, dict):
        codes = []
        for key, item in value.items():
            if isinstance(item, str) and _is_icd_code_key(key):
                codes.extend(_extract_icd_codes(item))
            elif isinstance(item, list | dict):
                codes.extend(_extract_icd_codes(item))
        return codes

    return []


def _normalize_icd_code(code: str) -> str:
    """Normalize ICD code casing while preserving the display dot."""
    return code.strip().upper()


def _icd_reference_url(code: str) -> str:
    """Build the icd.kcb.vn detail URL. Dots are removed from the id parameter."""
    icd_id = _normalize_icd_code(code).replace(".", "")
    return f"{ICD_REFERENCE_BASE_URL}?id={quote(icd_id, safe='')}&model=disease"


__all__ = ["check_icd"]
