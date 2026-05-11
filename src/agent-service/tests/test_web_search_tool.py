"""Tests for optional Tavily web-search dependency handling."""

import importlib.util
import sys
from pathlib import Path


def test_web_search_tool_loads_without_tavily(monkeypatch):
    """The skill module should import even when tavily-python is not installed."""
    tool_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "quality-agent"
        / "web-search"
        / "scripts"
        / "tool.py"
    )

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "tavily":
            raise ModuleNotFoundError("No module named 'tavily'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    module_name = "test_web_search_tool_without_tavily"
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader

    spec.loader.exec_module(module)
    result = module.web_search.invoke({"query": "ICD J02.9"})

    assert "tavily-python" in result
    assert "error" in result
