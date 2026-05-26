"""Tests for human review panel state selection helpers."""

import sys
import types
from importlib import import_module


def _install_optional_ui_stubs() -> None:
    streamlit = types.ModuleType("streamlit")
    streamlit.__getattr__ = lambda name: (lambda *args, **kwargs: None)
    sys.modules.setdefault("streamlit", streamlit)

    pandas = types.ModuleType("pandas")
    pandas.DataFrame = lambda *args, **kwargs: args[0] if args else []
    sys.modules.setdefault("pandas", pandas)


def _review_panel_module():
    _install_optional_ui_stubs()
    return import_module("interfaces.web.components.review_panel")


def test_final_review_displays_final_result():
    review_panel = _review_panel_module()
    state = {
        "review_stage": "final",
        "agent_1_result": {"decision": "accept", "message": "completeness"},
        "agent_2_result": {"decision": "accept", "message": "quality"},
        "final_result": {"decision": "reject", "message": "final reject"},
    }

    assert review_panel.get_pending_assessment(state) == state["final_result"]


def test_final_review_edit_payload_targets_quality_result():
    review_panel = _review_panel_module()
    state = {
        "review_stage": "final",
        "agent_2_result": {"decision": "accept_with_edit", "message": "quality edit"},
        "final_result": {"decision": "reject", "message": "final reject"},
    }

    assert review_panel.get_editable_assessment(state) == state["agent_2_result"]
