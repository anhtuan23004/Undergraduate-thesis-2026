"""Tests for ICD lookup tool response enrichment."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_check_icd_module():
    tool_path = (
        Path(__file__).parents[1] / "skills" / "quality-agent" / "check-icd" / "scripts" / "tool.py"
    )
    spec = importlib.util.spec_from_file_location("check_icd_tool_under_test", tool_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_icd_reference_url_removes_dot_from_id() -> None:
    module = _load_check_icd_module()

    assert (
        module._icd_reference_url("J00.1")
        == "https://icd.kcb.vn/icd-10/icd10?id=J001&model=disease"
    )


def test_extract_icd_codes_accepts_code_without_dot() -> None:
    module = _load_check_icd_module()

    assert module._extract_icd_codes("J001") == ["J001"]


def test_success_response_adds_reference_url_for_query_code() -> None:
    module = _load_check_icd_module()

    response = module._build_success_response("J18", {"description": "Viêm phổi"})

    assert response["reference_url"] == "https://icd.kcb.vn/icd-10/icd10?id=J18&model=disease"
    assert response["reference_urls"] == {
        "J18": "https://icd.kcb.vn/icd-10/icd10?id=J18&model=disease"
    }


def test_success_response_enriches_nested_icd_code_result() -> None:
    module = _load_check_icd_module()

    response = module._build_success_response(
        "viem mui hong",
        {"items": [{"icd_code": "J00.1", "name": "Viêm mũi họng cấp"}]},
    )

    item = response["result"]["items"][0]
    assert item["reference_url"] == "https://icd.kcb.vn/icd-10/icd10?id=J001&model=disease"
    assert response["reference_urls"]["J00.1"] == (
        "https://icd.kcb.vn/icd-10/icd10?id=J001&model=disease"
    )
