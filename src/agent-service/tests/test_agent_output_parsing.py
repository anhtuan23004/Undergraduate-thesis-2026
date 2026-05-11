"""Tests for agent output parsing helpers."""

from dataclasses import dataclass

from agents.output_parsing import extract_agent_content, parse_json_response


@dataclass
class Message:
    content: object


def test_extract_agent_content_from_text_message():
    result = {"messages": [Message(content="  hello  ")]}

    assert extract_agent_content(result) == "hello"


def test_extract_agent_content_from_list_blocks():
    result = {
        "messages": [
            Message(content=[{"text": "hello"}, " ", {"text": "world"}]),
        ]
    }

    assert extract_agent_content(result) == "hello world"


def test_parse_json_response_strips_markdown_fence():
    parsed = parse_json_response('```json\n{"decision": "accept"}\n```')

    assert parsed == {"decision": "accept"}


def test_parse_json_response_returns_default_error_shape():
    parsed = parse_json_response("not json")

    assert parsed["decision"] == "reject"
    assert parsed["rejection_reason"] == "Could not parse agent response"
