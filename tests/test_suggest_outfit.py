"""
Tests for suggest_outfit.

The Groq client is mocked throughout so no API key is needed.
Each test injects a fake LLM response and inspects:
  - the return value (type, non-empty guarantee, fallback)
  - the prompt that was actually sent to the LLM (branch selection, field inclusion)
"""

from unittest.mock import MagicMock, patch

from tools import suggest_outfit


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "category": "tops",
    "style_tags": ["vintage", "graphic tee", "streetwear"],
    "size": "M",
    "condition": "good",
    "price": 22.0,
    "colors": ["black", "white"],
    "brand": None,
    "platform": "depop",
    "description": "Faded bootleg-style tee with a worn-in feel.",
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans, dark wash",
            "category": "bottoms",
            "colors": ["dark blue", "indigo"],
            "style_tags": ["denim", "streetwear", "baggy"],
        },
        {
            "id": "w_007",
            "name": "Chunky white sneakers",
            "category": "shoes",
            "colors": ["white"],
            "style_tags": ["sneakers", "chunky", "streetwear"],
        },
    ]
}

EMPTY_WARDROBE = {"items": []}


def _make_mock_client(response_text: str) -> MagicMock:
    """Return a mock Groq client whose chat.completions.create yields response_text."""
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
    """Extract the user-role prompt string from the last LLM call."""
    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    return user_messages[-1]


# ── Return type & non-empty guarantee ────────────────────────────────────────

def test_returns_string():
    with patch("tools._get_groq_client", return_value=_make_mock_client("Try it with baggy jeans.")):
        result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)


def test_return_value_is_non_empty():
    with patch("tools._get_groq_client", return_value=_make_mock_client("Great look with your jeans.")):
        result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert len(result.strip()) > 0


def test_llm_returns_empty_string_triggers_fallback():
    with patch("tools._get_groq_client", return_value=_make_mock_client("")):
        result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert len(result.strip()) > 0


def test_llm_returns_whitespace_triggers_fallback():
    with patch("tools._get_groq_client", return_value=_make_mock_client("   \n  ")):
        result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert len(result.strip()) > 0


# ── LLM response is passed through ───────────────────────────────────────────

def test_llm_response_is_returned_verbatim():
    expected = "Pair it with your baggy jeans and chunky sneakers for a 90s vibe."
    with patch("tools._get_groq_client", return_value=_make_mock_client(expected)):
        result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert result == expected


def test_leading_trailing_whitespace_is_stripped():
    with patch("tools._get_groq_client", return_value=_make_mock_client("  Nice outfit.  ")):
        result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert result == "Nice outfit."


# ── Prompt branch: empty wardrobe ─────────────────────────────────────────────

def test_empty_wardrobe_calls_llm_once():
    mock_client = _make_mock_client("General style advice here.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    mock_client.chat.completions.create.assert_called_once()


def test_empty_wardrobe_prompt_contains_item_title():
    mock_client = _make_mock_client("Style it with wide-leg trousers.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    prompt = _captured_prompt(mock_client)
    assert SAMPLE_ITEM["title"] in prompt


def test_empty_wardrobe_prompt_does_not_contain_wardrobe_items():
    mock_client = _make_mock_client("Works well with slim trousers.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    prompt = _captured_prompt(mock_client)
    # Wardrobe item names must not appear since the wardrobe is empty
    assert "Baggy straight-leg jeans" not in prompt
    assert "Chunky white sneakers" not in prompt


# ── Prompt branch: wardrobe with items ───────────────────────────────────────

def test_wardrobe_branch_calls_llm_once():
    mock_client = _make_mock_client("Great pairing with your jeans.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    mock_client.chat.completions.create.assert_called_once()


def test_wardrobe_branch_prompt_contains_item_title():
    mock_client = _make_mock_client("Pair it with your dark jeans.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    prompt = _captured_prompt(mock_client)
    assert SAMPLE_ITEM["title"] in prompt


def test_wardrobe_branch_prompt_contains_all_wardrobe_item_names():
    mock_client = _make_mock_client("Looks great with your wardrobe.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    prompt = _captured_prompt(mock_client)
    for item in SAMPLE_WARDROBE["items"]:
        assert item["name"] in prompt, f"Expected '{item['name']}' in prompt"


def test_wardrobe_branch_prompt_contains_item_colors():
    mock_client = _make_mock_client("Looks great.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    prompt = _captured_prompt(mock_client)
    for color in SAMPLE_ITEM["colors"]:
        assert color in prompt


# ── Item field edge cases ─────────────────────────────────────────────────────

def test_item_with_no_brand_does_not_crash():
    item = {**SAMPLE_ITEM, "brand": None}
    with patch("tools._get_groq_client", return_value=_make_mock_client("Works well.")):
        result = suggest_outfit(item, EMPTY_WARDROBE)
    assert isinstance(result, str) and result


def test_item_with_empty_colors_list_does_not_crash():
    item = {**SAMPLE_ITEM, "colors": []}
    with patch("tools._get_groq_client", return_value=_make_mock_client("Works well.")):
        result = suggest_outfit(item, EMPTY_WARDROBE)
    assert isinstance(result, str) and result


def test_item_with_empty_style_tags_does_not_crash():
    item = {**SAMPLE_ITEM, "style_tags": []}
    with patch("tools._get_groq_client", return_value=_make_mock_client("Works well.")):
        result = suggest_outfit(item, EMPTY_WARDROBE)
    assert isinstance(result, str) and result


def test_item_with_missing_fields_does_not_crash():
    # Minimal item — only id present
    with patch("tools._get_groq_client", return_value=_make_mock_client("Works well.")):
        result = suggest_outfit({"id": "lst_min"}, EMPTY_WARDROBE)
    assert isinstance(result, str) and result


# ── Wardrobe shape edge cases ─────────────────────────────────────────────────

def test_wardrobe_missing_items_key_treated_as_empty():
    # wardrobe dict has no 'items' key at all
    mock_client = _make_mock_client("General advice.")
    with patch("tools._get_groq_client", return_value=mock_client):
        result = suggest_outfit(SAMPLE_ITEM, {})
    assert isinstance(result, str) and result
    # Should have taken the empty-wardrobe branch (no wardrobe item names in prompt)
    prompt = _captured_prompt(mock_client)
    assert "Baggy straight-leg jeans" not in prompt


def test_single_wardrobe_item():
    wardrobe = {
        "items": [
            {"id": "w_003", "name": "White ribbed tank top", "category": "tops", "colors": ["white"]}
        ]
    }
    mock_client = _make_mock_client("Try it over your white ribbed tank top.")
    with patch("tools._get_groq_client", return_value=mock_client):
        result = suggest_outfit(SAMPLE_ITEM, wardrobe)
    assert isinstance(result, str) and result
    prompt = _captured_prompt(mock_client)
    assert "White ribbed tank top" in prompt
