from langchain_core.tools import tool
from pydantic import BaseModel, Field


class CheckClaimHistoryInput(BaseModel):
    policy_number: str = Field(..., description="The policy number of the customer to check.")
    days: int = Field(
        30, description="The number of recent days to check for claim history (default is 30 days)."
    )


@tool("check_claim_history", args_schema=CheckClaimHistoryInput)
def check_claim_history(policy_number: str, days: int = 30) -> str:
    """
    Check the recent claim history for a given policy number within the specified number of days.
    Returns the total approved amount and the frequency of claims.
    This tool is critical for detecting 'Claim Splitting' (submitting multiple small claims to bypass Auto-Approve thresholds).
    """
    import asyncio

    from mongodb_client import get_recent_claims, get_recent_claims_total

    try:
        # Avoid async context issues by checking if there's a running loop
        try:
            _ = asyncio.get_running_loop()
            # We are in an async context but we need synchronous output for the tool
            # (LangChain tools can be async, but standard @tool uses sync)
            # Actually, we can just call it synchronously since it uses pymongo which is blocking.
        except RuntimeError:
            pass

        claims = get_recent_claims(policy_number, days)
        total_amount = get_recent_claims_total(policy_number, days)

        count = len(claims)
        if count == 0:
            return f"Không có hồ sơ bồi thường nào trong {days} ngày qua cho số hợp đồng {policy_number}."

        return (
            f"Phát hiện {count} hồ sơ đã được duyệt trong {days} ngày qua cho số hợp đồng {policy_number}.\n"
            f"Tổng số tiền đã bồi thường: {total_amount:,.0f} VNĐ."
        )
    except Exception as e:
        return f"Lỗi khi tra cứu lịch sử bồi thường: {str(e)}"
