"""
Tests for create_fit_card.

The Groq client is mocked throughout so no API key is needed.
The empty-outfit guard fires before the client is even created,
so those tests need no mock at all.
"""

from unittest.mock import MagicMock, patch

from tools import create_fit_card


# ── Shared fixtures ───────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "price": 22.0,
    "platform": "depop",
    "category": "tops",
    "colors": ["black", "white"],
    "style_tags": ["vintage", "graphic tee", "streetwear"],
    "condition": "good",
    "brand": None,
}

SAMPLE_OUTFIT = (
    "Pair this faded bootleg tee with your baggy dark-wash jeans and chunky white sneakers "
    "for a classic 90s streetwear look. Tuck the front hem slightly for shape."
)


def _make_mock_client(response_text: str) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = response_text

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def _captured_prompt(mock_client: MagicMock) -> str:
    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    return user_messages[-1]


# ── Empty / whitespace outfit guard (no LLM call needed) ────

def test_empty_outfit_returns_error_string():
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert result.startswith("Error:")


def test_whitespace_only_outfit_returns_error_string():
    result = create_fit_card("   \n\t  ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert result.startswith("Error:")


def test_empty_outfit_does_not_raise():
    try:
        create_fit_card("", SAMPLE_ITEM)
    except Exception as e:
        raise AssertionError(f"Expected no exception, got {type(e).__name__}: {e}")


def test_empty_outfit_does_not_call_llm():
    mock_client = _make_mock_client("some caption")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card("", SAMPLE_ITEM)
    mock_client.chat.completions.create.assert_not_called()


def test_error_string_is_non_empty():
    result = create_fit_card("", SAMPLE_ITEM)
    assert len(result.strip()) > 0


# ── Return type & non-empty guarantee (normal path) ──────────────────────────

def test_returns_string():
    with patch("tools._get_groq_client", return_value=_make_mock_client("Great caption here.")):
        result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert isinstance(result, str)


def test_return_value_is_non_empty():
    with patch("tools._get_groq_client", return_value=_make_mock_client("Great caption here.")):
        result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert len(result.strip()) > 0


def test_llm_empty_response_triggers_fallback():
    with patch("tools._get_groq_client", return_value=_make_mock_client("")):
        result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert len(result.strip()) > 0


def test_llm_whitespace_response_triggers_fallback():
    with patch("tools._get_groq_client", return_value=_make_mock_client("   \n  ")):
        result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert len(result.strip()) > 0


# ── LLM response pass-through ─────────────────────────────────────────────────

def test_llm_response_returned_verbatim():
    expected = "thrifted this bootleg tee off depop for $22 and it slaps with my baggy jeans."
    with patch("tools._get_groq_client", return_value=_make_mock_client(expected)):
        result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert result == expected


def test_leading_trailing_whitespace_stripped():
    with patch("tools._get_groq_client", return_value=_make_mock_client("  Nice caption.  ")):
        result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert result == "Nice caption."


def test_llm_called_once_on_normal_path():
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    mock_client.chat.completions.create.assert_called_once()


# ── Prompt content ────────────────────────────────────────────────────────────

def test_prompt_contains_item_title():
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert SAMPLE_ITEM["title"] in _captured_prompt(mock_client)


def test_prompt_contains_platform():
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert SAMPLE_ITEM["platform"] in _captured_prompt(mock_client)


def test_prompt_contains_formatted_price():
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert "$22" in _captured_prompt(mock_client)


def test_prompt_contains_outfit_text():
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert SAMPLE_OUTFIT.strip() in _captured_prompt(mock_client)


# ── High temperature for variance ─────────────────────────────────────────────

def test_llm_called_with_high_temperature():
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] > 1.0


# ── Missing item fields ───────────────────────────────────────────────────────

def test_missing_price_uses_fallback_label():
    item = {**SAMPLE_ITEM}
    del item["price"]
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        result = create_fit_card(SAMPLE_OUTFIT, item)
    assert isinstance(result, str) and result
    assert "a steal" in _captured_prompt(mock_client)


def test_missing_platform_does_not_crash():
    item = {**SAMPLE_ITEM}
    del item["platform"]
    with patch("tools._get_groq_client", return_value=_make_mock_client("A caption.")):
        result = create_fit_card(SAMPLE_OUTFIT, item)
    assert isinstance(result, str) and result


def test_missing_title_does_not_crash():
    item = {**SAMPLE_ITEM}
    del item["title"]
    with patch("tools._get_groq_client", return_value=_make_mock_client("A caption.")):
        result = create_fit_card(SAMPLE_OUTFIT, item)
    assert isinstance(result, str) and result


def test_empty_item_dict_does_not_crash():
    with patch("tools._get_groq_client", return_value=_make_mock_client("A caption.")):
        result = create_fit_card(SAMPLE_OUTFIT, {})
    assert isinstance(result, str) and result


def test_price_zero_formatted_correctly():
    item = {**SAMPLE_ITEM, "price": 0.0}
    mock_client = _make_mock_client("A caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card(SAMPLE_OUTFIT, item)
    assert "$0" in _captured_prompt(mock_client)
