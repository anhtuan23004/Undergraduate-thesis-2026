from eval.token_usage import estimate_tokens, token_usage_from_metadata


def test_estimate_tokens_uses_four_character_heuristic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_token_usage_prefers_provider_metadata():
    usage = token_usage_from_metadata(
        {"usage_metadata": {"input_tokens": 10, "output_tokens": 5}},
        prompt_text="ignored",
        completion_text="ignored",
    )

    assert usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "token_usage": 15,
        "token_usage_source": "provider_metadata",
    }


def test_token_usage_falls_back_to_char_estimate():
    usage = token_usage_from_metadata({}, prompt_text="abcdefgh", completion_text="abcd")

    assert usage == {
        "prompt_tokens": 2,
        "completion_tokens": 1,
        "token_usage": 3,
        "token_usage_source": "char_estimate",
    }
