"""Web search tool for medical information using Tavily.

This tool allowing the agent to search the web for medical information,
drug details, or insurance policy updates.
"""

import json

from config import settings
from langchain_core.tools import tool

try:
    from tavily import TavilyClient
except ModuleNotFoundError:
    TavilyClient = None


def _get_tavily_client():
    """Create Tavily client only when the optional API key is configured."""
    if TavilyClient is None:
        return None
    if not settings.TAVILY_API_KEY:
        return None
    return TavilyClient(api_key=settings.TAVILY_API_KEY)


@tool("web-search")
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web for medical information as a fallback.

    ONLY use this tool if internal databases (like search-medicine or check-icd)
    return no results or insufficient information. This tool is for finding
    missing medications, rare diseases, or latest insurance policies on the web.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default: 2).

    Returns:
        JSON string with search results.
    """
    if TavilyClient is None:
        return json.dumps(
            {
                "status": "error",
                "message": "Optional dependency 'tavily-python' is not installed",
            },
            ensure_ascii=False,
        )

    tavily_client = _get_tavily_client()
    if tavily_client is None:
        return json.dumps(
            {"status": "error", "message": "TAVILY_API_KEY not configured or invalid"}
        )

    try:
        search_results = tavily_client.search(
            query=query, search_depth="basic", max_results=max_results
        )

        formatted_results = []
        for res in search_results.get("results", []):
            formatted_results.append(
                {
                    "title": res.get("title", ""),
                    "content": res.get("content", ""),
                    "url": res.get("url", ""),
                }
            )

        return json.dumps(
            {"status": "success", "query": query, "results": formatted_results}, ensure_ascii=False
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


__all__ = ["web_search"]
