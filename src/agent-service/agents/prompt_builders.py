"""Prompt builders for LangGraph agent nodes."""

import json
from typing import Any

from graphs.workflow_policy import review_target_from_state


def build_base_prompt(state: dict[str, Any], _agent_name: str) -> str:
    """Build a minimal fallback prompt."""
    claim_id = state.get("claim_id", "N/A")
    policy_number = state.get("policy_number", "N/A")
    return f"Process claim {claim_id} for policy {policy_number}"


def build_completeness_prompt(state: dict[str, Any], _agent_name: str) -> str:
    """Build prompt for the completeness agent."""
    claim_id = state.get("claim_id", "N/A")
    policy_number = state.get("policy_number", "N/A")
    input_file = state.get("input_file", "N/A")
    ocr_stage = state.get("ocr_stage") or state.get("extracted_documents", {}).get("ocr_stage")
    extracted = _json_block(state.get("extracted_documents", {}))

    return (
        f"Kiểm toán tính đầy đủ của hồ sơ bảo hiểm {claim_id}. Số hợp đồng: {policy_number}\n"
        f"Tài liệu đầu vào: {input_file}\n\n"
        f"<ocr_stage>\n{ocr_stage or 'unknown'}\n</ocr_stage>\n\n"
        "Ở bước Completeness, nếu ocr_stage là phase1_classified thì dữ liệu OCR mới chỉ "
        "gồm classification/segmentation; chưa có extracted_data chi tiết. Hãy dùng "
        "documents làm nguồn chính để kiểm tra nhóm chứng từ bắt buộc.\n\n"
        f"<extracted_documents>\n{extracted}\n</extracted_documents>\n\n"
        f"<history_summary>\n{_history_summary(state)}\n</history_summary>\n"
    )


def build_quality_prompt(state: dict[str, Any], _agent_name: str) -> str:
    """Build prompt for the medical quality agent."""
    claim_id = state.get("claim_id", "N/A")
    policy_number = state.get("policy_number", "N/A")
    extracted = _json_block(state.get("extracted_documents", {}))

    return (
        f"Xác minh chất lượng y tế cho hồ sơ {claim_id}. Số hợp đồng: {policy_number}\n\n"
        f"<extracted_documents>\n{extracted}\n</extracted_documents>\n\n"
        f"<history_summary>\n{_history_summary(state)}\n</history_summary>\n"
    )


def build_decision_prompt(state: dict[str, Any], _agent_name: str) -> str:
    """Build prompt for the final decision agent."""
    claim_id = state.get("claim_id", "N/A")
    policy_number = state.get("policy_number", "N/A")
    completeness = _json_block(state.get("agent_1_result", {}))
    quality = _json_block(state.get("agent_2_result", {}))
    human_review = _json_block(state.get("human_review_result", {}))

    return (
        f"Đưa ra quyết định cuối cùng cho hồ sơ {claim_id}. Số hợp đồng: {policy_number}\n\n"
        f"<completeness_result>\n{completeness}\n</completeness_result>\n\n"
        f"<quality_result>\n{quality}\n</quality_result>\n\n"
        f"<human_review_result>\n{human_review}\n</human_review_result>\n"
    )


def build_verifier_prompt(state: dict[str, Any], _agent_name: str) -> str:
    """Build prompt for the skeptical verifier agent."""
    claim_id = state.get("claim_id", "N/A")
    input_file = state.get("input_file", "N/A")
    primary_assessment = _primary_assessment_for_review(state)
    evidence = primary_assessment.get("evidence", {})

    return (
        f"Thẩm định chéo kết quả đánh giá cho hồ sơ {claim_id}.\n"
        f"Tài liệu gốc: {input_file}\n\n"
        f"<primary_assessment>\n{_json_block(primary_assessment)}\n</primary_assessment>\n\n"
        f"<extracted_evidence>\n{_json_block(evidence)}\n</extracted_evidence>\n\n"
        f"<extracted_documents>\n{_json_block(state.get('extracted_documents', {}))}\n"
        f"</extracted_documents>\n"
    )


def build_schema_output_instruction(schema_class: Any) -> str:
    """Build JSON schema instruction for schema-bound agent outputs."""
    schema_dict = schema_class.model_json_schema()
    if "properties" in schema_dict:
        schema_dict["properties"].pop("is_auto_reviewed", None)

    schema_json = json.dumps(schema_dict, ensure_ascii=False)
    return (
        "\n\n<output_format>\n"
        "Bạn phải trả về kết quả tuân thủ chính xác lược đồ JSON sau:\n"
        f"{schema_json}\n</output_format>"
    )


def _history_summary(state: dict[str, Any]) -> str:
    history_list = state.get("history", [])[-2:]
    if not history_list:
        return "Chưa có"
    return "\n".join(
        f"- Bước {entry.get('step', 'unknown')} ({entry.get('agent', 'System')}): Đã xử lý"
        for entry in history_list
    )


def _primary_assessment_for_review(state: dict[str, Any]) -> dict[str, Any]:
    return review_target_from_state(state).result


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)
