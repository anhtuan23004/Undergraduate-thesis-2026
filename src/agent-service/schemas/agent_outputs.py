"""Pydantic schemas for structured agent outputs."""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


class Issue(BaseModel):
    """Represents a single issue found during assessment."""

    severity: Literal["critical", "high", "medium", "low"] = Field(description="Mức độ nghiêm trọng của vấn đề")
    code: str = Field(description="Mã lỗi (VD: MISSING_DOC, INVALID_ICD)")
    description: str = Field(description="Mô tả chi tiết vấn đề bằng tiếng Việt")
    reason: str = Field(default="", description="Lý do tại sao đây là vấn đề (giải trình)")


class SuggestedUpdate(BaseModel):
    """A single suggested edit proposed by the agent."""

    field: str = Field(description="Tên trường cần sửa (VD: icd_code, medication)")
    current_value: Optional[str] = Field(default=None, description="Giá trị hiện tại trong hồ sơ")
    suggested_value: str = Field(description="Giá trị gợi ý thay thế")
    reference_url: Optional[str] = Field(
        default=None,
        description="URL tham chiếu để người dùng verify (VD: link tra cứu ICD, link thuốc)",
    )


class QualityWarning(BaseModel):
    """Medical quality warning or alert."""

    type: str = Field(description="Loại cảnh báo (icd_missing, icd_mismatch, excluded_diagnosis, medicine_mismatch)")
    diagnosis_name: str = Field(description="Tên chẩn đoán/thuốc liên quan")
    suggested_icd: Optional[str] = Field(default=None, description="Mã ICD gợi ý (nếu có)")
    message: str = Field(description="Mô tả chi tiết lý do cảnh báo")
    reference_url: Optional[str] = Field(default=None, description="URL tham chiếu để xác thực cảnh báo")


class QualitySuccess(BaseModel):
    """Medical quality success or approved item."""

    type: str = Field(description="Loại thành công (icd_valid, coverage_approved, medicine_valid)")
    diagnosis_name: str = Field(description="Tên chẩn đoán/thuốc liên quan")
    icd: Optional[str] = Field(default=None, description="Mã ICD đã xác thực")
    message: str = Field(description="Mô tả chi tiết")
    reference_url: Optional[str] = Field(default=None, description="URL tham chiếu (nếu có)")


class MedicalQualityData(BaseModel):
    """Encapsulated medical quality results."""

    summary: Dict[str, int] = Field(description="Tóm tắt số lượng (total_warnings, total_success)")
    warnings: List[QualityWarning] = Field(default_factory=list, description="Danh sách các cảnh báo y tế")
    success: List[QualitySuccess] = Field(default_factory=list, description="Danh sách các mục đã xác thực thành công")


class MedicalQualityFindings(BaseModel):
    """Structured medical quality findings for the Quality Agent."""

    status_message: Literal["success", "Warning"] = Field(description="Trạng thái tổng quát của đợt kiểm tra")
    data: MedicalQualityData = Field(description="Dữ liệu chi tiết về cảnh báo và thành công")


class AssessmentOutput(BaseModel):
    """Output for Completeness and Quality agents."""

    valid: bool = Field(description="Đánh giá tổng quan xem hợp lệ hay không")
    decision: Literal["accept", "reject", "accept_with_edit"] = Field(description="Quyết định tại bước này")
    issues: List[Issue] = Field(default_factory=list, description="Danh sách các vấn đề phát hiện được")
    message: str = Field(description="Tóm tắt lý do quyết định bằng tiếng Việt")
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của kết quả đánh giá (0.0 - 1.0)",
    )
    is_auto_reviewed: bool = Field(
        default=False,
        description="Đánh dấu kết quả đã được Agent tự động duyệt",
    )
    suggested_updates: Optional[List[SuggestedUpdate]] = Field(
        default=None,
        description="Danh sách gợi ý sửa đổi kèm link tham chiếu",
    )
    evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bằng chứng trích xuất từ tài liệu (tài liệu, chẩn đoán, thuốc, tổng tiền...)",
    )
    medical_findings: Optional[MedicalQualityFindings] = Field(
        default=None,
        description="Kết quả kiểm tra y tế chi tiết (success/warnings)",
    )


class IssueSummary(BaseModel):
    category: Literal["completeness", "quality", "policy"] = Field(description="Phân loại nhóm vấn đề")
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
    issues_summary: List[IssueSummary] = Field(default_factory=list, description="Tóm tắt tổng hợp các vấn đề")
    message: str = Field(description="Giải thích rõ ràng bằng tiếng Việt về lý do đưa ra quyết định")
