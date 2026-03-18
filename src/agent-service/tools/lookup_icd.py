"""ICD lookup tool for diagnosis verification."""

import json
import os
from urllib.parse import quote

import requests
from langchain_core.tools import tool

ICD10_BASE_URL = os.getenv("ICD10_BASE_URL", "https://ccs.whiteneuron.com/api/ICD10/search")


@tool
def lookup_icd(query: str) -> str:
    """Look up ICD entries by diagnosis text or ICD code and return JSON."""
    if not query or not query.strip():
        return json.dumps({"status": "error", "message": "query is required", "results": []})

    try:
        response = requests.get(
            f"{ICD10_BASE_URL}/{quote(query.strip(), safe='')}",
            params={"lang": "vi", "vol1": 1, "vol3": 0, "html": "true"},
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "message": f"lookup failed: {exc}",
                "results": [],
            },
            ensure_ascii=False,
        )

    try:
        payload = response.json()
        if isinstance(payload, dict):
            return json.dumps(
                {
                    "status": "success",
                    "query": query,
                    "result": payload,
                },
                ensure_ascii=False,
            )
    except Exception:
        pass

    return json.dumps(
        {
            "status": "success",
            "query": query,
            "result": response.text,
        },
        ensure_ascii=False,
    )
