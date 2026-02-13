"""Coverage calculation tool."""
from typing import Any, Dict, List

from tools.base import BaseTool


# Mock policy data
DEFAULT_POLICY_INFO = {
    "annual_limit": 100_000_000,
    "deductible": 5_000_000,
    "copay_rate": 0.15,
    "ytd_claims": 0
}

MOCK_POLICY_DATA = {
    "POL-001": {
        "annual_limit": 500_000_000,
        "deductible": 5_000_000,
        "copay_rate": 0.1,
        "ytd_claims": 50_000_000
    },
    "POL-002": {
        "annual_limit": 200_000_000,
        "deductible": 10_000_000,
        "copay_rate": 0.2,
        "ytd_claims": 20_000_000
    }
}


class CoverageCalcTool(BaseTool):
    """Tool for calculating eligible claim amounts."""

    name = "coverage_calc"
    description = "Calculate eligible claim amounts after deductibles and copayments"

    async def arun(
        self,
        claimed_amounts: List[float],
        policy_number: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Calculate coverage.

        Args:
            claimed_amounts: List of claimed amounts
            policy_number: Policy number

        Returns:
            Calculation breakdown
        """
        if not claimed_amounts:
            return {
                "status": "error",
                "message": "No amounts provided",
                "summary": "Missing claim amounts"
            }

        policy_info = self._get_policy_info(policy_number)
        total_claimed = sum(claimed_amounts)

        # Apply deductible
        after_deductible = max(0, total_claimed - policy_info["deductible"])
        deductible_applied = min(total_claimed, policy_info["deductible"])

        # Apply copay
        copay_amount = after_deductible * policy_info["copay_rate"]
        after_copay = after_deductible - copay_amount

        # Check annual limit
        remaining_limit = policy_info["annual_limit"] - policy_info.get("ytd_claims", 0)
        eligible_amount = min(after_copay, remaining_limit)
        limit_reduction = after_copay - eligible_amount

        return {
            "status": "success",
            "calculation": {
                "total_claimed": total_claimed,
                "deductible_applied": deductible_applied,
                "copay_rate": policy_info["copay_rate"],
                "copay_amount": copay_amount,
                "eligible_amount": eligible_amount,
                "limit_reduction": limit_reduction,
                "remaining_annual_limit": remaining_limit - eligible_amount
            },
            "summary": f"Total: {total_claimed:,.0f} VND, Eligible: {eligible_amount:,.0f} VND"
        }

    def _get_policy_info(self, policy_number: str) -> Dict[str, Any]:
        """Get policy limits (mock)."""
        return MOCK_POLICY_DATA.get(policy_number, DEFAULT_POLICY_INFO)
