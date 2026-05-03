"""Pydantic schemas for verifier agent outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class VerifierOutput(BaseModel):
    """Output for the Verifier Agent.

    The Verifier Agent cross-checks a primary assessment for contradictions.
    It returns a verdict ('pass'/'fail') with reasoning and a list of
    specific contradictions found.
    """

    verdict: Literal["pass", "fail"] = Field(description="Kết quả thẩm định")
    reason: str = Field(description="Giải trình chi tiết lý do pass/fail bằng tiếng Việt")
    contradictions: list[str] = Field(
        default_factory=list, description="Danh sách các điểm mâu thuẫn tìm thấy"
    )
