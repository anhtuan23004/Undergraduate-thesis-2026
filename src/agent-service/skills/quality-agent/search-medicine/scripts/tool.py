"""Medicine search tool using MongoDB text search.

This tool wraps the existing search_medicine function for use with the skill-based architecture.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from langchain_core.tools import tool

from mongodb_client import get_medicine_collection


def build_medical_search_pipeline(raw_user_input: str):
    """Build an Atlas Search pipeline from user text."""
    words = raw_user_input.split()
    name_clauses = []
    unit_clauses = []

    for word in words:
        if any(char.isdigit() for char in word):
            unit_clauses.append({"text": {"query": word, "path": "name"}})
        else:
            name_clauses.append(
                {
                    "text": {
                        "query": word,
                        "path": "name",
                        "fuzzy": {
                            "maxEdits": 2,
                            "prefixLength": 1,
                            "maxExpansions": 50,
                        },
                    }
                }
            )

    main_compound = {}
    if name_clauses:
        main_compound["must"] = [{"compound": {"should": name_clauses, "minimumShouldMatch": 1}}]

    if unit_clauses:
        if not name_clauses:
            main_compound["must"] = unit_clauses
        else:
            main_compound["should"] = unit_clauses

    return [
        {"$search": {"index": "hybrid-full-text-search", "compound": main_compound}},
        {"$limit": 1},
        {"$project": {"_id": 0, "name": 1, "usage": 1, "careful": 1}},
    ]


def search_single_medicine(medicine_name: str) -> dict:
    """Search one medicine entry."""
    collection = get_medicine_collection()
    pipeline = build_medical_search_pipeline(medicine_name)
    results = list(collection.aggregate(pipeline))
    return {"query": medicine_name, "results": results}


@tool("search-medicine")
def search_medicine(medicine_names: List[str]) -> str:
    """Search medicines in parallel and return JSON result.

    This tool searches for medications in the MongoDB medicine collection
    to verify prescribed medications against standard medical database.

    Args:
        medicine_names: List of medicine names to search

    Returns:
        JSON string with search results
    """
    if not medicine_names:
        return json.dumps({"error": "No medicine names provided", "results": []})

    if isinstance(medicine_names, str):
        medicine_names = [medicine_names]

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(medicine_names), 10)) as executor:
        future_to_name = {
            executor.submit(search_single_medicine, name): name for name in medicine_names
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = {
                    "query": name,
                    "error": str(exc),
                    "results": [],
                    "count": 0,
                }

    return json.dumps({"results": results}, ensure_ascii=False)


__all__ = ["search_medicine"]
