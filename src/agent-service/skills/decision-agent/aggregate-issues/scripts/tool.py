"""Issue aggregation tool for final decision making.

This tool aggregates issues identified by completeness and quality agents
to produce a final decision recommendation.
"""

import json
from typing import Any

from langchain_core.tools import tool


@tool("aggregate-issues")
def aggregate_issues(  # noqa: C901
    completeness_result: dict[str, Any] | None = None,
    quality_result: dict[str, Any] | None = None,
    human_review_notes: str | None = None,
) -> str:
    """Aggregate issues from all verification stages and generate final decision recommendation.

    This tool synthesizes findings from document completeness checks, medical quality
    audits, and human review notes to produce a final coverage decision.

    Args:
        completeness_result: Result from completeness check agent
        quality_result: Result from quality check agent
        human_review_notes: Optional notes from human reviewer

    Returns:
        JSON string with aggregated issues and recommended decision
    """
    completeness_issues = []
    quality_issues = []

    if completeness_result:
        if "issues" in completeness_result:
            completeness_issues = completeness_result["issues"]
        elif isinstance(completeness_result, dict):
            for _key, value in completeness_result.items():
                if isinstance(value, dict) and "issues" in value:
                    completeness_issues.extend(value["issues"])

    if quality_result:
        if "issues" in quality_result:
            quality_issues = quality_result["issues"]
        elif isinstance(quality_result, dict):
            for _key, value in quality_result.items():
                if isinstance(value, dict) and "issues" in value:
                    quality_issues.extend(value["issues"])

    all_issues = completeness_issues + quality_issues

    return json.dumps(
        {
            "completeness_issues": completeness_issues,
            "quality_issues": quality_issues,
            "total_issues": len(all_issues),
            "human_review_notes": human_review_notes,
        },
        ensure_ascii=False,
    )


__all__ = ["aggregate_issues"]
