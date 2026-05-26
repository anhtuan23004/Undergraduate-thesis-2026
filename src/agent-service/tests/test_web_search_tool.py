"""Tests for optional Tavily web-search dependency handling."""

import importlib.util
import json
import sys
from pathlib import Path


def _load_web_search_module(module_name: str = "test_web_search_tool"):
    tool_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "quality-agent"
        / "web-search"
        / "scripts"
        / "tool.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_web_search_tool_loads_without_tavily(monkeypatch):
    """The skill module should import even when tavily-python is not installed."""

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "tavily":
            raise ModuleNotFoundError("No module named 'tavily'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    module = _load_web_search_module("test_web_search_tool_without_tavily")
    result = module.web_search.invoke({"query": "thuốc không có trong CSDL"})

    assert "tavily-python" in result
    assert "error" in result


def test_web_search_compacts_and_ranks_medicine_results(monkeypatch):
    module = _load_web_search_module("test_web_search_tool_medicine")

    class FakeTavilyClient:
        last_kwargs = None

        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, **kwargs):
            FakeTavilyClient.last_kwargs = kwargs
            return {
                "answer": "Paracetamol được dùng để giảm đau và hạ sốt.",
                "results": [
                    {
                        "title": "Shopping result",
                        "content": "Mua thuốc giá bao nhiêu",
                        "url": "https://example.com/paracetamol",
                        "score": 0.99,
                    },
                    {
                        "title": "Paracetamol 500mg công dụng chỉ định",
                        "content": "Thuốc Paracetamol 500mg có công dụng giảm đau hạ sốt.",
                        "raw_content": (
                            "Paracetamol 500mg được chỉ định để điều trị đau nhẹ đến "
                            "vừa và hạ sốt ở bệnh nhân. Số đăng ký VD-12345-67."
                        ),
                        "url": "https://trungtamthuoc.com/paracetamol-500mg",
                        "score": 0.2,
                    },
                ],
            }

    monkeypatch.setattr(module, "TavilyClient", FakeTavilyClient)
    monkeypatch.setattr(module.settings, "TAVILY_API_KEY", "test-key")

    raw_result = module.web_search.invoke(
        {"query": "thuốc Paracetamol 500mg công dụng", "max_results": 3}
    )
    result = json.loads(raw_result)

    assert result["status"] == "success"
    assert result["query"] == "thuốc Paracetamol 500mg công dụng"
    assert len(result["results"]) == 1
    assert result["results"][0]["domain"] == "trungtamthuoc.com"
    assert "usage_evidence" in result["results"][0]
    assert result["results"][0]["registration_numbers"] == ["VD-12345-67"]
    assert FakeTavilyClient.last_kwargs["include_domains"] == module.MEDICINE_INFO_DOMAINS
    assert FakeTavilyClient.last_kwargs["include_raw_content"] == "text"


def test_web_search_rejects_icd_queries_without_calling_tavily(monkeypatch):
    module = _load_web_search_module("test_web_search_tool_icd")

    class FakeTavilyClient:
        called = False

        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, **kwargs):
            FakeTavilyClient.called = True
            return {"results": []}

    monkeypatch.setattr(module, "TavilyClient", FakeTavilyClient)
    monkeypatch.setattr(module.settings, "TAVILY_API_KEY", "test-key")

    raw_result = module.web_search.invoke({"query": "ICD J02.9", "max_results": 2})
    result = json.loads(raw_result)

    assert result["status"] == "error"
    assert result["results"] == []
    assert "check-icd" in result["message"]
    assert FakeTavilyClient.called is False


def test_web_search_keeps_non_icd_generic_queries_unrestricted(monkeypatch):
    module = _load_web_search_module("test_web_search_tool_generic")

    class FakeTavilyClient:
        last_kwargs = None

        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, **kwargs):
            FakeTavilyClient.last_kwargs = kwargs
            return {
                "results": [
                    {
                        "title": "Insurance policy update",
                        "content": "Coverage policy update.",
                        "url": "https://policy.example/update",
                    }
                ],
            }

    monkeypatch.setattr(module, "TavilyClient", FakeTavilyClient)
    monkeypatch.setattr(module.settings, "TAVILY_API_KEY", "test-key")

    raw_result = module.web_search.invoke(
        {"query": "latest health insurance policy", "max_results": 2}
    )
    result = json.loads(raw_result)

    assert result["status"] == "success"
    assert result["results"][0]["title"] == "Insurance policy update"
    assert "include_domains" not in FakeTavilyClient.last_kwargs
    assert "include_raw_content" not in FakeTavilyClient.last_kwargs
