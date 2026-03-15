"""Aggregate issues tool for multi-agent system.

This module implements the AggregateIssuesTool which combines validation
results from multiple agents and generates a recommendation based on
severity-weighted analysis.
"""

from typing import Any, Dict, List, Optional

from core.base.tool import BaseTool
from config import settings


class AggregateIssuesTool(BaseTool):
    """Tool for aggregating validation issues from multiple agents.

    This tool combines issues from different validation agents, applies
    severity weighting, and generates an overall recommendation for
    claim processing.

    Severity weights (higher = more severe):
    - critical: 4
    - high: 3
    - medium: 2
    - low: 1
    """

    name: str = "aggregate_issues"
    description: str = (
        "Aggregate validation issues from multiple agents and generate "
        "a recommendation based on severity-weighted analysis. "
        "Combines issues from agent_1, agent_2, and human review."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_1_result": {
                "type": "object",
                "description": "Validation result from agent 1",
                "properties": {
                    "issues": {
                        "type": "array",
                        "description": "List of issues found by agent 1",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "high", "medium", "low"],
                                    "description": "Severity level of the issue"
                                },
                                "message": {
                                    "type": "string",
                                    "description": "Description of the issue"
                                },
                                "field": {
                                    "type": "string",
                                    "description": "Field or document related to the issue"
                                }
                            },
                            "required": ["severity", "message"]
                        }
                    },
                    "valid": {
                        "type": "boolean",
                        "description": "Whether agent 1 validation passed"
                    }
                }
            },
            "agent_2_result": {
                "type": "object",
                "description": "Validation result from agent 2",
                "properties": {
                    "issues": {
                        "type": "array",
                        "description": "List of issues found by agent 2",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "high", "medium", "low"],
                                    "description": "Severity level of the issue"
                                },
                                "message": {
                                    "type": "string",
                                    "description": "Description of the issue"
                                },
                                "field": {
                                    "type": "string",
                                    "description": "Field or document related to the issue"
                                }
                            },
                            "required": ["severity", "message"]
                        }
                    },
                    "valid": {
                        "type": "boolean",
                        "description": "Whether agent 2 validation passed"
                    }
                }
            },
            "human_review_result": {
                "type": "object",
                "description": "Validation result from human review",
                "properties": {
                    "issues": {
                        "type": "array",
                        "description": "List of issues found by human review",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "high", "medium", "low"],
                                    "description": "Severity level of the issue"
                                },
                                "message": {
                                    "type": "string",
                                    "description": "Description of the issue"
                                },
                                "field": {
                                    "type": "string",
                                    "description": "Field or document related to the issue"
                                }
                            },
                            "required": ["severity", "message"]
                        }
                    },
                    "valid": {
                        "type": "boolean",
                        "description": "Whether human review validation passed"
                    }
                }
            }
        },
        "required": ["agent_1_result", "agent_2_result", "human_review_result"]
    }

    # Severity weights for scoring (higher = more severe)
    SEVERITY_WEIGHTS = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1
    }

    # Thresholds for recommendations - loaded from settings
    # Note: These can be overridden via environment variables or .env file
    CRITICAL_THRESHOLD = settings.CRITICAL_THRESHOLD   # Any critical issue triggers rejection
    HIGH_THRESHOLD = settings.HIGH_THRESHOLD          # 3+ high severity issues trigger rejection
    MEDIUM_THRESHOLD = settings.MEDIUM_THRESHOLD     # 5+ medium severity issues trigger review
    SCORE_THRESHOLD = settings.SCORE_THRESHOLD       # Weighted score threshold for rejection

    async def execute(
        self,
        agent_1_result: Dict[str, Any],
        agent_2_result: Dict[str, Any],
        human_review_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the aggregate issues tool.

        Combines all issues from different agents, calculates severity-weighted
        scores, and generates a recommendation.

        Args:
            agent_1_result: Validation result from agent 1 containing 'issues'
                list and 'valid' boolean.
            agent_2_result: Validation result from agent 2 containing 'issues'
                list and 'valid' boolean.
            human_review_result: Validation result from human review containing
                'issues' list and 'valid' boolean.

        Returns:
            A dictionary containing:
            - success: True if aggregation succeeded
            - aggregated_issues: Combined list of all issues with source info
            - summary: Count of issues by severity and source
            - recommendation: Overall recommendation (approve, review, reject)
            - recommendation_reason: Explanation for the recommendation
            - weighted_score: Total severity-weighted score
        """
        try:
            # Extract issues from each result
            agent_1_issues = agent_1_result.get("issues", [])
            agent_2_issues = agent_2_result.get("issues", [])
            human_issues = human_review_result.get("issues", [])

            # Combine all issues with source attribution
            aggregated_issues = []

            for issue in agent_1_issues:
                aggregated_issues.append({
                    **issue,
                    "source": "agent_1"
                })

            for issue in agent_2_issues:
                aggregated_issues.append({
                    **issue,
                    "source": "agent_2"
                })

            for issue in human_issues:
                aggregated_issues.append({
                    **issue,
                    "source": "human_review"
                })

            # Calculate severity counts
            severity_counts = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            }

            for issue in aggregated_issues:
                severity = issue.get("severity", "low")
                if severity in severity_counts:
                    severity_counts[severity] += 1

            # Calculate source-specific counts
            source_counts = {
                "agent_1": len(agent_1_issues),
                "agent_2": len(agent_2_issues),
                "human_review": len(human_issues)
            }

            # Calculate weighted score
            weighted_score = self._calculate_weighted_score(aggregated_issues)

            # Generate recommendation
            recommendation, reason = await self._generate_recommendation(
                aggregated_issues,
                severity_counts,
                weighted_score,
                agent_1_result.get("valid", True),
                agent_2_result.get("valid", True),
                human_review_result.get("valid", True)
            )

            return {
                "success": True,
                "aggregated_issues": aggregated_issues,
                "summary": {
                    "total_issues": len(aggregated_issues),
                    "by_severity": severity_counts,
                    "by_source": source_counts
                },
                "recommendation": recommendation,
                "recommendation_reason": reason,
                "weighted_score": weighted_score
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to aggregate issues: {str(e)}",
                "aggregated_issues": [],
                "summary": {},
                "recommendation": "review",
                "recommendation_reason": "Error during aggregation, manual review required",
                "weighted_score": 0
            }

    def _calculate_weighted_score(self, issues: List[Dict[str, Any]]) -> int:
        """Calculate the total severity-weighted score for all issues.

        Args:
            issues: List of issue dictionaries with 'severity' key.

        Returns:
            Total weighted score sum of all issues.
        """
        total_score = 0
        for issue in issues:
            severity = issue.get("severity", "low")
            weight = self.SEVERITY_WEIGHTS.get(severity, 1)
            total_score += weight
        return total_score

    async def _generate_recommendation(
        self,
        issues: List[Dict[str, Any]],
        severity_counts: Dict[str, int],
        weighted_score: int,
        agent_1_valid: bool,
        agent_2_valid: bool,
        human_valid: bool
    ) -> tuple[str, str]:
        """Generate a recommendation based on aggregated issues.

        Recommendation logic:
        - REJECT: Any critical issues, 3+ high issues, or weighted score >= 8
        - REVIEW: 5+ medium issues, weighted score >= 5, or any agent flagged invalid
        - APPROVE: No significant issues found

        Args:
            issues: List of all aggregated issues.
            severity_counts: Dictionary of issue counts by severity.
            weighted_score: Total severity-weighted score.
            agent_1_valid: Whether agent 1 validation passed.
            agent_2_valid: Whether agent 2 validation passed.
            human_valid: Whether human review validation passed.

        Returns:
            Tuple of (recommendation, reason) where recommendation is one of
            "approve", "review", or "reject".
        """
        reasons = []

        # Check for critical issues
        if severity_counts.get("critical", 0) >= self.CRITICAL_THRESHOLD:
            reasons.append(f"Found {severity_counts['critical']} critical issue(s)")

        # Check for high severity issues
        if severity_counts.get("high", 0) >= self.HIGH_THRESHOLD:
            reasons.append(f"Found {severity_counts['high']} high severity issues (threshold: {self.HIGH_THRESHOLD})")

        # Check for medium severity issues
        if severity_counts.get("medium", 0) >= self.MEDIUM_THRESHOLD:
            reasons.append(f"Found {severity_counts['medium']} medium severity issues (threshold: {self.MEDIUM_THRESHOLD})")

        # Check weighted score
        if weighted_score >= self.SCORE_THRESHOLD:
            reasons.append(f"Weighted score {weighted_score} exceeds threshold {self.SCORE_THRESHOLD}")

        # Check agent validation results
        if not agent_1_valid:
            reasons.append("Agent 1 validation failed")
        if not agent_2_valid:
            reasons.append("Agent 2 validation failed")
        if not human_valid:
            reasons.append("Human review flagged issues")

        # Determine recommendation
        if severity_counts.get("critical", 0) > 0 or severity_counts.get("high", 0) >= self.HIGH_THRESHOLD or weighted_score >= self.SCORE_THRESHOLD:
            recommendation = "reject"
            reason = "; ".join(reasons) if reasons else "Critical issues or high severity threshold exceeded"
        elif severity_counts.get("medium", 0) >= self.MEDIUM_THRESHOLD or weighted_score >= 5 or not agent_1_valid or not agent_2_valid:
            recommendation = "review"
            reason = "; ".join(reasons) if reasons else "Medium severity issues or validation failed"
        else:
            recommendation = "approve"
            reason = "No significant issues found"

        return recommendation, reason
