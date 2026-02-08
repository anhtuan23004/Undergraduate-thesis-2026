"""Policy check tool."""
import httpx
from typing import Any, Dict

from tools.base import BaseTool
from app.config import settings


class PolicyCheckTool(BaseTool):
    """Tool for checking policy coverage."""

    name = "policy_check"
    description = "Check insurance policy terms, coverage limits, and exclusions"

    async def arun(
        self,
        policy_number: str,
        query: str = "general coverage",
        **kwargs
    ) -> Dict[str, Any]:
        """Check policy information.

        Args:
            policy_number: Insurance policy number
            query: Specific query about policy

        Returns:
            Policy information
        """
        if not policy_number:
            return {
                "status": "error",
                "message": "No policy number provided",
                "summary": "Missing policy number"
            }

        # TODO: Connect to RAG service for actual policy lookup
        # For now, return mock data

        mock_policies = {
            "POL-001": {
                "status": "active",
                "plan": "Premium Health",
                "annual_limit": 500_000_000,  # 500M VND
                "deductible": 5_000_000,  # 5M VND
                "copay_rate": 0.1,  # 10%
                "waiting_period_days": 30,
                "exclusions": ["cosmetic surgery", "pre-existing conditions"]
            },
            "POL-002": {
                "status": "active",
                "plan": "Standard Health",
                "annual_limit": 200_000_000,  # 200M VND
                "deductible": 10_000_000,  # 10M VND
                "copay_rate": 0.2,  # 20%
                "waiting_period_days": 60,
                "exclusions": ["cosmetic surgery", "dental", "vision"]
            }
        }

        policy = mock_policies.get(policy_number, {
            "status": "active",
            "plan": "Standard",
            "annual_limit": 100_000_000,
            "deductible": 5_000_000,
            "copay_rate": 0.15,
            "waiting_period_days": 30,
            "exclusions": ["cosmetic surgery"]
        })

        # Check if query matches exclusions
        query_lower = query.lower()
        is_excluded = any(excl in query_lower for excl in policy.get("exclusions", []))

        return {
            "status": "success",
            "policy_number": policy_number,
            "policy": policy,
            "is_active": policy["status"] == "active",
            "may_be_excluded": is_excluded,
            "summary": f"Policy {policy_number}: {policy['plan']}, Limit: {policy['annual_limit']:,} VND"
        }
