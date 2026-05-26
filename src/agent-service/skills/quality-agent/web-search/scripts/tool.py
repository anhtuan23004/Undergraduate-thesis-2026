"""Web search tool for medical information using Tavily.

This tool allows the agent to search the web for medicine information.
"""

import json
import re
from typing import Any
from urllib.parse import urlparse

from config import settings
from langchain_core.tools import tool

try:
    from tavily import TavilyClient
except ModuleNotFoundError:
    TavilyClient = None

MAX_WEB_RESULTS = 3
MAX_ANSWER_CHARS = 700
MAX_CONTENT_CHARS = 500
MAX_TITLE_CHARS = 120
MAX_USAGE_EVIDENCE_CHARS = 900

MEDICINE_INFO_DOMAINS = [
    "trungtamthuoc.com",
    "thuocbietduoc.com.vn",
    "nhathuocthanthien.com.vn",
    "vnras.com",
    "nhathuoclongchau.com.vn",
    "trungsoncare.com",
]

ALLOWED_MEDICINE_DOMAINS = set(MEDICINE_INFO_DOMAINS)

MEDICINE_INFO_SIGNALS = {
    "usage": ("công dụng", "chỉ định", "điều trị"),
    "registration": ("số đăng ký", "sđk", "sdk", "registration"),
    "composition": ("hoạt chất", "thành phần"),
    "form_strength": ("dạng bào chế", "hàm lượng", "nồng độ"),
    "category": ("nhóm thuốc", "phân loại", "danh mục"),
}

USAGE_SECTION_KEYWORDS = (
    "chỉ định",
    "công dụng",
    "tác dụng",
    "indications",
    "indications/uses",
    "therapeutic indications",
    "uses",
)

USAGE_PHRASE_KEYWORDS = (
    "được chỉ định",
    "được dùng",
    "dùng để",
    "dùng trong",
    "sử dụng để",
    "sử dụng trong",
    "có tác dụng",
    "điều trị",
    "hỗ trợ điều trị",
    "dự phòng",
    "phòng ngừa",
    "làm giảm",
    "giúp giảm",
    "indicated",
    "used for",
    "used to",
    "treatment of",
    "prevention of",
    "relief of",
)

CLINICAL_CONTEXT_KEYWORDS = (
    "bệnh",
    "triệu chứng",
    "nhiễm",
    "viêm",
    "đau",
    "sốt",
    "co thắt",
    "dị ứng",
    "huyết",
    "áp lực",
    "phù",
    "suy",
    "thiếu",
    "tăng",
    "giảm",
    "kiểm soát",
    "cải thiện",
    "cấp",
    "mạn",
    "patient",
    "patients",
    "disease",
    "symptom",
    "infection",
    "inflammation",
    "pain",
    "fever",
    "pressure",
    "acute",
    "chronic",
)

NOISE_KEYWORDS = (
    "giỏ hàng",
    "hotline",
    "hỗ trợ khách hàng",
    "nhập email",
    "danh mục",
    "đăng nhập",
    "sản phẩm này chỉ",
    "sản phẩm thay thế",
    "sản phẩm cùng hoạt chất",
    "cùng hoạt chất",
    "cùng thành phần hoạt chất",
    "sản phẩm liên quan",
    "tham khảo một số thuốc",
    "biệt dược chứa",
    "thông tin chi tiết về",
    "để biết thêm thông tin",
    "cung cấp thông tin chính xác",
    "giá sản phẩm",
    "giá bao nhiêu",
    "mua ở đâu",
)

TITLE_STOPWORDS = {
    "thuốc",
    "công",
    "dụng",
    "chỉ",
    "định",
    "điều",
    "trị",
    "lưu",
    "khi",
    "dùng",
    "mua",
    "giá",
    "bao",
    "nhiêu",
    "chính",
    "hãng",
    "inj",
}

REGISTRATION_PATTERN = re.compile(
    r"\b(?:VD|VN|VNB|GC|QL|SDK|SĐK)[-/]?\d[\w./-]*\b",
    re.IGNORECASE,
)


def _get_tavily_client():
    """Create Tavily client only when the optional API key is configured."""
    if TavilyClient is None:
        return None
    if not settings.TAVILY_API_KEY:
        return None
    return TavilyClient(api_key=settings.TAVILY_API_KEY)


def _truncate(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _domain_from_url(url: str) -> str:
    return urlparse(url or "").netloc.replace("www.", "")


def _is_allowed_domain(result: dict) -> bool:
    domain = _domain_from_url(result.get("url", ""))
    return domain in ALLOWED_MEDICINE_DOMAINS


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_noise_segment(segment: str) -> bool:
    lower_segment = segment.lower()
    return any(keyword in lower_segment for keyword in NOISE_KEYWORDS)


def _title_tokens(result: dict) -> tuple[str, ...]:
    title = str(result.get("title") or "").lower()
    tokens = re.findall(r"[a-zA-ZÀ-ỹ0-9%/-]+", title)
    return tuple(token for token in tokens if len(token) >= 4 and token not in TITLE_STOPWORDS)


def _usage_score(text: str, title_tokens: tuple[str, ...] = ()) -> int:
    lower_text = text.lower()
    section_score = sum(1 for keyword in USAGE_SECTION_KEYWORDS if keyword in lower_text)
    phrase_score = sum(1 for keyword in USAGE_PHRASE_KEYWORDS if keyword in lower_text)
    context_score = sum(1 for keyword in CLINICAL_CONTEXT_KEYWORDS if keyword in lower_text)
    title_score = sum(1 for token in title_tokens if token in lower_text)
    noise_penalty = sum(1 for keyword in NOISE_KEYWORDS if keyword in lower_text)
    length_bonus = min(len(text) // 180, 3)
    return (
        section_score * 3
        + phrase_score * 4
        + context_score
        + title_score * 6
        + length_bonus
        - noise_penalty * 4
    )


def _usage_snippet(
    segments: list[str],
    index: int,
    title_tokens: tuple[str, ...],
) -> str:
    parts = [segments[index]]
    for next_segment in segments[index + 1 : index + 3]:
        if _is_noise_segment(next_segment):
            continue
        candidate = " ".join([*parts, next_segment])
        if len(candidate) > 520:
            break
        if _usage_score(next_segment, title_tokens) > 0:
            parts.append(next_segment)

    return _truncate(" ".join(parts), 520)


def _usage_evidence(result: dict) -> str:
    raw_text = str(result.get("raw_content") or result.get("content") or "")
    if not raw_text.strip():
        return ""

    title_tokens = _title_tokens(result)
    segments = [_normalize_text(segment) for segment in re.split(r"(?<=[.!?])\s+|\n+", raw_text)]
    segments = [
        segment for segment in segments if len(segment) >= 40 and not _is_noise_segment(segment)
    ]

    candidates = []
    for index, segment in enumerate(segments):
        score = _usage_score(segment, title_tokens)
        if not score:
            continue
        candidates.append((score, index, _usage_snippet(segments, index, title_tokens)))

    if not candidates:
        return ""

    selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:3]
    selected = sorted(selected, key=lambda item: item[1])

    snippets = []
    seen = set()
    for _, _, snippet in selected:
        normalized_snippet = snippet.lower()
        if normalized_snippet in seen:
            continue
        snippets.append(snippet)
        seen.add(normalized_snippet)
        if len(" ".join(snippets)) >= MAX_USAGE_EVIDENCE_CHARS:
            break

    return _truncate(" ".join(snippets), MAX_USAGE_EVIDENCE_CHARS)


def _medicine_signals(result: dict, extra_text: str = "") -> list[str]:
    text = " ".join(
        str(result.get(field, "")) for field in ("title", "content", "raw_content", "url")
    ).lower()
    if extra_text:
        text = f"{text} {extra_text.lower()}"

    signals = [
        signal
        for signal, keywords in MEDICINE_INFO_SIGNALS.items()
        if any(keyword in text for keyword in keywords)
    ]
    if REGISTRATION_PATTERN.search(text) and "registration" not in signals:
        signals.append("registration")
    return signals


def _registration_numbers(result: dict, extra_text: str = "") -> list[str]:
    text = " ".join(
        str(result.get(field, "")) for field in ("title", "content", "raw_content", "url")
    )
    if extra_text:
        text = f"{text} {extra_text}"
    return list(dict.fromkeys(REGISTRATION_PATTERN.findall(text)))


def _result_quality(result: dict) -> float:
    usage_evidence = _usage_evidence(result)
    tavily_score = result.get("score") or 0
    try:
        tavily_score = float(tavily_score)
    except (TypeError, ValueError):
        tavily_score = 0

    usage_bonus = 5 if usage_evidence else 0
    return len(_medicine_signals(result, usage_evidence)) * 10 + usage_bonus + tavily_score


def _compact_result(result: dict) -> dict:
    url = result.get("url", "")
    compact = {
        "title": _truncate(result.get("title"), MAX_TITLE_CHARS),
        "content": _truncate(result.get("content"), MAX_CONTENT_CHARS),
        "url": url,
    }

    usage_evidence = _usage_evidence(result)
    compact["domain"] = _domain_from_url(url)
    if usage_evidence:
        compact["usage_evidence"] = usage_evidence
    signals = _medicine_signals(result, usage_evidence)
    if signals:
        compact["signals"] = signals
    registration_numbers = _registration_numbers(result, usage_evidence)
    if registration_numbers:
        compact["registration_numbers"] = registration_numbers
    return compact


def _compact_response(
    response: dict,
    *,
    max_results: int,
) -> dict:
    raw_results = response.get("results") or []
    raw_results = [result for result in raw_results if _is_allowed_domain(result)]
    ranked_results = sorted(raw_results, key=_result_quality, reverse=True)

    selected_results = ranked_results[: min(max_results, MAX_WEB_RESULTS)]
    compact = {
        "status": "success",
        "answer": _truncate(response.get("answer"), MAX_ANSWER_CHARS),
        "results": [_compact_result(result) for result in selected_results],
    }
    return compact


@tool("web-search")
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web for medicine information as a fallback.

    ONLY use this tool if search-medicine returns no results or insufficient
    information. This tool is for finding missing medication details on the web.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default: 2).

    Returns:
        JSON string with search results.
    """
    if not query or not query.strip():
        return json.dumps(
            {"status": "error", "message": "No query provided", "results": []},
            ensure_ascii=False,
        )

    if TavilyClient is None:
        return json.dumps(
            {
                "status": "error",
                "message": "Optional dependency 'tavily-python' is not installed",
            },
            ensure_ascii=False,
        )

    tavily_client = _get_tavily_client()
    if tavily_client is None:
        return json.dumps(
            {"status": "error", "message": "TAVILY_API_KEY not configured or invalid"}
        )

    try:
        requested_results = max(1, min(max_results, MAX_WEB_RESULTS))
        search_kwargs = {
            "query": query,
            "search_depth": "basic",
            "max_results": max(5, requested_results),
            "include_domains": MEDICINE_INFO_DOMAINS,
            "include_answer": "advanced",
            "include_raw_content": "text",
        }

        search_results = tavily_client.search(
            **search_kwargs,
        )

        compact_results = _compact_response(
            search_results,
            max_results=requested_results,
        )
        compact_results["query"] = query
        return json.dumps(compact_results, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


__all__ = ["web_search"]
