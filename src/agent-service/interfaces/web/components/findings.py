"""Rendering helpers for findings, evidence, and suggested updates."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .constants import SEVERITY_COLORS


def render_issue_details(issues: list[dict]) -> None:
    """Render issue list in a clear and reviewer-friendly format."""
    st.markdown("**Lỗi / Cảnh báo chi tiết**")

    rows = []
    for issue in issues:
        severity = str(issue.get("severity", "low")).lower()
        icon = SEVERITY_COLORS.get(severity, "⚪")
        code = issue.get("code") or issue.get("category") or "-"
        description = issue.get("description") or issue.get("message") or "-"
        reason = issue.get("reason") or "-"
        count = issue.get("count")

        if count is not None:
            description = f"{description} (số lượng: {count})"

        rows.append(
            {
                "Mức độ": f"{icon} {severity.upper()}",
                "Mã/Nhóm": str(code),
                "Mô tả": str(description),
                "Lý do": str(reason),
            }
        )

    if not rows:
        st.caption("Không có lỗi/cảnh báo")
        return

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Mức độ": st.column_config.TextColumn("Mức độ", width="small"),
            "Mã/Nhóm": st.column_config.TextColumn("Mã/Nhóm", width="small"),
            "Mô tả": st.column_config.TextColumn("Mô tả", width="medium"),
            "Lý do": st.column_config.TextColumn("Lý do", width="medium"),
        },
    )


def render_confidence_badge(payload: dict) -> None:
    """Display a color-coded confidence score badge."""
    confidence = payload.get("confidence_score")
    if confidence is None:
        return

    is_auto = payload.get("is_auto_reviewed", False)
    auto_tag = " · ✅ Đã duyệt tự động" if is_auto else ""

    if confidence >= 0.9:
        color = "green"
    elif confidence >= 0.7:
        color = "orange"
    else:
        color = "red"

    st.markdown(f":{color}-badge[Độ tin cậy: {confidence:.0%}]{auto_tag}")


def render_medical_findings(findings: dict) -> None:  # noqa: C901
    """Render structured medical findings from Quality Agent."""
    if not findings:
        return

    st.markdown("---")
    st.markdown("### 🔍 Kết quả thẩm định y tế chi tiết")

    data = findings.get("data", {})
    summary = data.get("summary", {})
    total_w = summary.get("total_warnings", 0)
    total_s = summary.get("total_success", 0)

    status = findings.get("status_message", "Warning")
    if status.lower() == "success":
        st.success(f"✅ Hợp lệ: {total_s} danh mục")
    else:
        st.warning(f"⚠️ Cảnh báo: {total_w} lỗi/nghi vấn")

    type_labels = {
        "icd_valid": "Mã ICD hợp lệ",
        "coverage_approved": "Đã duyệt quyền lợi",
        "medicine_valid": "Thuốc hợp lệ",
        "icd_missing": "Thiếu mã ICD",
        "icd_mismatch": "Mã ICD không khớp",
        "excluded_diagnosis": "Bệnh lý loại trừ",
        "medicine_mismatch": "Thuốc không phù hợp",
        "name_consistent": "Họ tên đồng nhất",
        "prescription_date_valid": "Ngày kê đơn hợp lệ",
    }

    def clean(val):
        return val if val and str(val).lower() != "none" else "—"

    warnings_list = data.get("warnings", [])
    if warnings_list:
        st.markdown("**🚨 Cảnh báo & Sai sót**")
        for warning in warnings_list:
            warning_type = warning.get("type", "")
            diag = clean(warning.get("diagnosis_name"))
            icd = clean(warning.get("suggested_icd"))
            msg = clean(warning.get("message"))
            url = warning.get("reference_url")

            content = f"{msg}"
            if diag != "—":
                content = f"**{diag}** - {content}"
            if icd != "—":
                content = f"[{icd}] {content}"
            if url:
                content += f" ([Tham chiếu]({url}))"

            label = type_labels.get(warning_type, warning_type.replace("_", " ").title())
            st.markdown(f"- **{label}:** {content}")

    success_list = data.get("success", [])
    if success_list:
        st.markdown("**✅ Các mục đã xác thực**")
        for success in success_list:
            success_type = success.get("type", "")
            diag = clean(success.get("diagnosis_name"))
            icd = clean(success.get("icd"))
            msg = clean(success.get("message"))
            url = success.get("reference_url")

            content = f"{msg}"
            if diag != "—":
                content = f"**{diag}** - {content}"
            if icd != "—":
                content = f"[{icd}] {content}"
            if url:
                content += f" ([Tham chiếu]({url}))"

            label = type_labels.get(success_type, success_type.replace("_", " ").title())
            st.markdown(f"- **{label}:** {content}")


def render_evidence_panel(evidence: dict, step_key: str = "") -> None:  # noqa: C901
    """Display extracted evidence with a compact reviewer layout."""
    with st.expander("📋 Bằng chứng trích xuất từ tài liệu", expanded=False):
        low_conf_fields = evidence.get("low_confidence_fields", [])
        if low_conf_fields:
            st.error(
                f"🔴 Có {len(low_conf_fields)} trường dữ liệu trích xuất OCR có độ tin cậy thấp. Vui lòng đối chiếu lại với chứng từ gốc.",
                icon="⚠️",
            )

        def format_val(key, value):
            if value is None:
                return "—"
            if key == "icd_codes" and isinstance(value, list):
                return ", ".join(
                    f"{item.get('code', '')} ({item.get('diagnosis', '')})"
                    if isinstance(item, dict)
                    else str(item)
                    for item in value
                )
            if key == "medications" and isinstance(value, list):
                return ", ".join(
                    f"{item.get('name', '')} ({item.get('quantity', '')})"
                    if isinstance(item, dict)
                    else str(item)
                    for item in value
                )
            if isinstance(value, list):
                return ", ".join(str(v) for v in value) if value else "—"
            if isinstance(value, int | float) and "amount" in key.lower():
                return f"{value:,.0f} VNĐ"
            return str(value)

        field_labels = {
            "patient_name": "👤 Họ và tên",
            "policy_number": "🆔 Số hợp đồng",
            "benefit_type": "💡 Loại quyền lợi",
            "treatment_type": "🏥 Hình thức điều trị",
            "treatment_date": "📅 Ngày điều trị",
            "documents_found": "✅ Tài liệu tìm thấy",
            "documents_missing": "❌ Tài liệu thiếu",
            "diagnoses": "🩺 Chẩn đoán",
            "icd_codes": "🔤 Mã ICD",
            "medications": "💊 Danh mục thuốc",
            "total_claim_amount": "💰 Tổng tiền yêu cầu",
            "total_amount": "💰 Tổng tiền yêu cầu",
            "exclusions_found": "🚫 Loại trừ phát hiện",
            "medical_facility": "🏢 Cơ sở y tế",
            "hospital": "🏢 Bệnh viện/Phòng khám",
        }

        rendered_keys = set()
        internal_keys = {
            "history",
            "data",
            "is_auto_reviewed",
            "confidence_score",
            "low_confidence_fields",
        }

        def render_field(key_list, default_label=None):
            """Render the first available key in key_list and mark all as rendered."""
            low_conf_fields = evidence.get("low_confidence_fields", [])
            for key in key_list:
                if key in evidence and key not in rendered_keys:
                    val = evidence[key]
                    label = field_labels.get(key, default_label or key.replace("_", " ").title())
                    formatted_val = format_val(key, val)

                    if key in low_conf_fields:
                        st.markdown(f"- **{label}:** :red[{formatted_val}] ⚠️")
                    else:
                        st.write(f"- **{label}:** {formatted_val}")

                    rendered_keys.update(key_list)
                    return True
            return False

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Thông tin chung**")
            render_field(["patient_name"])
            render_field(["policy_number"])
            render_field(["benefit_type"])
            render_field(["treatment_type"])
            render_field(["treatment_date"])

        with col2:
            st.markdown("**Chứng từ**")
            render_field(["documents_found"])
            render_field(["documents_missing"])

        if step_key in {"completeness", "completeness_check"}:
            return

        st.divider()
        st.markdown("**Thông tin y tế**")
        render_field(["diagnoses"])
        render_field(["icd_codes"])
        render_field(["medications"])

        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("**Tài chính**")
            render_field(["total_claim_amount", "total_amount"])

        with col4:
            st.markdown("**Rủi ro & Loại trừ**")
            render_field(["exclusions_found"])

        leftover_keys = set(evidence.keys()) - rendered_keys - internal_keys
        if leftover_keys:
            st.divider()
            with st.status("📌 Dữ liệu bổ sung khác...", expanded=False):
                for key in sorted(leftover_keys):
                    label = field_labels.get(key, key.replace("_", " ").title())
                    st.write(f"- **{label}:** {format_val(key, evidence[key])}")


def render_suggested_updates(  # noqa: C901
    suggested_updates: list, step_key: str = "unknown", column_labels: dict | None = None
) -> None:
    """Display suggested edits with reference URLs."""
    if not suggested_updates:
        return

    groups = {"default": []}
    if step_key == "quality":
        groups = {"icd": [], "medication": []}

    for suggested_update in suggested_updates:
        if not isinstance(suggested_update, dict):
            continue

        url = str(suggested_update.get("reference_url", "")).lower()

        if step_key == "quality":
            if "icd" in url or "kcb.vn" in url:
                groups["icd"].append(suggested_update)
            else:
                groups["medication"].append(suggested_update)
        else:
            groups["default"].append(suggested_update)

    for group_type, items in groups.items():
        if not items:
            continue

        if group_type == "icd":
            labels = {
                "field": "Chẩn đoán",
                "current_value": "ICD trong hồ sơ",
                "suggested_value": "ICD gợi ý",
                "reference_url": "Link tham chiếu",
            }
            title = f"✏️ Gợi ý chỉnh sửa ICD ({len(items)})"
        elif group_type == "medication":
            labels = {
                "field": "Thuốc",
                "current_value": "Chi tiết",
                "suggested_value": "Khuyến nghị",
                "reference_url": "Link tham chiếu",
            }
            title = f"💊 Gợi ý chỉnh sửa Thuốc ({len(items)})"
        else:
            labels = column_labels or {
                "field": "Trường",
                "current_value": "Giá trị hiện tại",
                "suggested_value": "Gợi ý",
                "reference_url": "Link tham chiếu",
            }
            title = f"✏️ Gợi ý chỉnh sửa ({len(items)})"

        with st.expander(title, expanded=True):
            rows = []
            for suggested_update in items:
                url = suggested_update.get("reference_url") or ""
                rows.append(
                    {
                        labels["field"]: suggested_update.get("field", "-"),
                        labels["current_value"]: suggested_update.get("current_value") or "—",
                        labels["suggested_value"]: suggested_update.get("suggested_value", "-"),
                        labels["reference_url"]: url if url else "—",
                    }
                )

            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        labels["field"]: st.column_config.TextColumn(
                            labels["field"], width="small"
                        ),
                        labels["current_value"]: st.column_config.TextColumn(
                            labels["current_value"], width="medium"
                        ),
                        labels["suggested_value"]: st.column_config.TextColumn(
                            labels["suggested_value"], width="medium"
                        ),
                        labels["reference_url"]: st.column_config.LinkColumn(
                            labels["reference_url"], width="small"
                        ),
                    },
                )


_render_confidence_badge = render_confidence_badge
_render_evidence_panel = render_evidence_panel
_render_issue_details = render_issue_details
_render_medical_findings = render_medical_findings
_render_suggested_updates = render_suggested_updates
