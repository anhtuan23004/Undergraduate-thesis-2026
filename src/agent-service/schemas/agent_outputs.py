"""Pydantic schemas for structured agent outputs."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Issue(BaseModel):
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Mức độ nghiêm trọng của vấn đề"
    )
    code: str = Field(description="Mã lỗi (VD: MISSING_DOC, INVALID_ICD)")
    description: str = Field(description="Mô tả chi tiết vấn đề bằng tiếng Việt")


class AssessmentOutput(BaseModel):
    """Output for Completeness and Quality agents."""
    valid: bool = Field(description="Đánh giá tổng quan xem hợp lệ hay không")
    decision: Literal["accept", "reject", "accept_with_edit"] = Field(
        description="Quyết định tại bước này"
    )
    issues: List[Issue] = Field(
        default_factory=list, description="Danh sách các vấn đề phát hiện được"
    )
    message: str = Field(description="Tóm tắt lý do quyết định bằng tiếng Việt")


class IssueSummary(BaseModel):
    category: Literal["completeness", "quality", "policy"] = Field(
        description="Phân loại nhóm vấn đề"
    )
    count: int = Field(description="Số lượng lỗi trong nhóm này")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Mức độ nghiêm trọng lớn nhất trong nhóm"
    )


class FinalDecisionOutput(BaseModel):
    """Output for the Final Decision agent."""
    decision: Literal["approve", "reject"] = Field(description="Quyết định cuối cùng")
    approved_amount: Optional[int] = Field(
        description="Số tiền phê duyệt (trả về 0 hoặc null nếu bị reject)", default=0
    )
    rejection_reason: Optional[str] = Field(
        description="Lý do từ chối chi tiết bằng tiếng Việt, hoặc null nếu approve", default=None
    )
    issues_summary: List[IssueSummary] = Field(
        default_factory=list, description="Tóm tắt tổng hợp các vấn đề"
    )
    message: str = Field(description="Giải thích rõ ràng bằng tiếng Việt về lý do đưa ra quyết định")
