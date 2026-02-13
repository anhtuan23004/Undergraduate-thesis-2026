"""Policy check tool."""
from typing import Any, Dict

from tools.base import BaseTool


# Mock policy data
DEFAULT_POLICY = {
    "status": "active",
    "plan": "Standard",
    "annual_limit": 100_000_000,
    "deductible": 5_000_000,
    "copay_rate": 0.15,
    "waiting_period_days": 30,
    "exclusions": ["cosmetic surgery"]
}

MOCK_POLICIES = {
    "POL-001": {
        "status": "active",
        "plan": "Premium Health",
        "annual_limit": 500_000_000,
        "deductible": 5_000_000,
        "copay_rate": 0.1,
        "waiting_period_days": 30,
        "exclusions": ["cosmetic surgery", "pre-existing conditions"]
    },
    "POL-002": {
        "status": "active",
        "plan": "Standard Health",
        "annual_limit": 200_000_000,
        "deductible": 10_000_000,
        "copay_rate": 0.2,
        "waiting_period_days": 60,
        "exclusions": ["cosmetic surgery", "dental", "vision"]
    }
}


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

        policy = MOCK_POLICIES.get(policy_number, DEFAULT_POLICY)
        is_excluded = self._check_exclusion(query, policy.get("exclusions", []))

        return {
            "status": "success",
            "policy_number": policy_number,
            "policy": policy,
            "is_active": policy["status"] == "active",
            "may_be_excluded": is_excluded,
            "summary": f"Policy {policy_number}: {policy['plan']}, Limit: {policy['annual_limit']:,} VND"
        }

    def _check_exclusion(self, query: str, exclusions: list) -> bool:
        """Check if query matches any exclusions."""
        query_lower = query.lower()
        return any(excl in query_lower for excl in exclusions)
