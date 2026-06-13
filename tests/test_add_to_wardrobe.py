"""
Tests for add_to_wardrobe.

No LLM calls — this tool is pure data manipulation, so no mocking needed.
"""

import pytest

from tools import add_to_wardrobe


# ── Fixtures ──────────────────────────────────────────────────────────────────

LISTING_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "category": "tops",
    "colors": ["black", "white"],
    "style_tags": ["vintage", "streetwear"],
    "price": 22.0,
    "platform": "depop",
    "condition": "good",
    "brand": None,
}

DESCRIBED_ITEM = {
    "name": "Black combat boots",
    "category": "shoes",
    "colors": ["black"],
    "style_tags": ["grunge", "boots"],
    "notes": "Lace-up, mid-ankle height",
}

EMPTY_WARDROBE = {"items": []}

SEEDED_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans, dark wash",
            "category": "bottoms",
            "colors": ["dark blue"],
            "style_tags": ["denim", "streetwear"],
        }
    ]
}


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_tuple():
    result = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, tuple) and len(result) == 2


def test_first_element_is_dict():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert isinstance(wardrobe, dict)


def test_second_element_is_string():
    _, msg = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert isinstance(msg, str)


# ── Success: listing dict (title → name mapping) ──────────────────────────────

def test_listing_item_added_to_empty_wardrobe():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert len(wardrobe["items"]) == 1


def test_listing_title_mapped_to_name():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["name"] == LISTING_ITEM["title"]


def test_listing_id_preserved():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["id"] == LISTING_ITEM["id"]


def test_listing_colors_preserved():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["colors"] == LISTING_ITEM["colors"]


def test_listing_style_tags_preserved():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["style_tags"] == LISTING_ITEM["style_tags"]


def test_listing_category_preserved():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["category"] == LISTING_ITEM["category"]


def test_success_confirmation_contains_item_name():
    _, msg = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert LISTING_ITEM["title"] in msg


# ── Success: user-described item (name key used directly) ─────────────────────

def test_described_item_added():
    wardrobe, _ = add_to_wardrobe(DESCRIBED_ITEM, EMPTY_WARDROBE)
    assert len(wardrobe["items"]) == 1


def test_described_item_name_used_directly():
    wardrobe, _ = add_to_wardrobe(DESCRIBED_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["name"] == DESCRIBED_ITEM["name"]


def test_described_item_notes_included():
    wardrobe, _ = add_to_wardrobe(DESCRIBED_ITEM, EMPTY_WARDROBE)
    assert wardrobe["items"][0].get("notes") == DESCRIBED_ITEM["notes"]


def test_described_item_auto_id_generated():
    # No 'id' key on the input — function must generate one
    wardrobe, _ = add_to_wardrobe(DESCRIBED_ITEM, EMPTY_WARDROBE)
    assert "id" in wardrobe["items"][0]
    assert wardrobe["items"][0]["id"]  # non-empty


# ── Notes field ───────────────────────────────────────────────────────────────

def test_item_without_notes_has_no_notes_key():
    item = {**LISTING_ITEM}  # listing has no 'notes'
    wardrobe, _ = add_to_wardrobe(item, EMPTY_WARDROBE)
    assert "notes" not in wardrobe["items"][0]


def test_item_with_notes_persists_notes():
    item = {**LISTING_ITEM, "notes": "Slightly cropped"}
    wardrobe, _ = add_to_wardrobe(item, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["notes"] == "Slightly cropped"


# ── Duplicate guard ───────────────────────────────────────────────────────────

def test_duplicate_id_returns_original_wardrobe_unchanged():
    wardrobe_after_first, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    wardrobe_after_second, _ = add_to_wardrobe(LISTING_ITEM, wardrobe_after_first)
    assert len(wardrobe_after_second["items"]) == 1


def test_duplicate_id_message_mentions_skipping():
    wardrobe, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    _, msg = add_to_wardrobe(LISTING_ITEM, wardrobe)
    msg_lower = msg.lower()
    assert "already" in msg_lower or "skip" in msg_lower


# ── Missing required fields ───────────────────────────────────────────────────

def test_missing_name_and_title_returns_error():
    _, msg = add_to_wardrobe({"category": "tops", "colors": ["red"]}, EMPTY_WARDROBE)
    assert "error" in msg.lower() or "missing" in msg.lower()


def test_missing_name_leaves_wardrobe_unchanged():
    wardrobe, _ = add_to_wardrobe({"category": "tops"}, SEEDED_WARDROBE)
    assert len(wardrobe["items"]) == len(SEEDED_WARDROBE["items"])


def test_missing_category_returns_error():
    _, msg = add_to_wardrobe({"name": "Mystery jacket"}, EMPTY_WARDROBE)
    assert "error" in msg.lower() or "missing" in msg.lower()


def test_missing_category_leaves_wardrobe_unchanged():
    wardrobe, _ = add_to_wardrobe({"name": "Mystery jacket"}, SEEDED_WARDROBE)
    assert len(wardrobe["items"]) == len(SEEDED_WARDROBE["items"])


def test_empty_item_dict_returns_error():
    _, msg = add_to_wardrobe({}, EMPTY_WARDROBE)
    assert isinstance(msg, str) and msg


# ── Optional fields default gracefully ───────────────────────────────────────

def test_missing_colors_defaults_to_empty_list():
    item = {"id": "x1", "title": "Plain Tee", "category": "tops"}
    wardrobe, _ = add_to_wardrobe(item, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["colors"] == []


def test_missing_style_tags_defaults_to_empty_list():
    item = {"id": "x2", "title": "Plain Tee", "category": "tops"}
    wardrobe, _ = add_to_wardrobe(item, EMPTY_WARDROBE)
    assert wardrobe["items"][0]["style_tags"] == []


# ── Wardrobe immutability ─────────────────────────────────────────────────────

def test_original_wardrobe_not_mutated():
    original_count = len(EMPTY_WARDROBE["items"])
    add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    assert len(EMPTY_WARDROBE["items"]) == original_count


def test_seeded_wardrobe_not_mutated():
    original_count = len(SEEDED_WARDROBE["items"])
    add_to_wardrobe(LISTING_ITEM, SEEDED_WARDROBE)
    assert len(SEEDED_WARDROBE["items"]) == original_count


# ── Sequential adds ───────────────────────────────────────────────────────────

def test_two_different_items_both_added():
    w1, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    w2, _ = add_to_wardrobe(DESCRIBED_ITEM, w1)
    assert len(w2["items"]) == 2


def test_second_add_appends_to_end():
    w1, _ = add_to_wardrobe(LISTING_ITEM, EMPTY_WARDROBE)
    w2, _ = add_to_wardrobe(DESCRIBED_ITEM, w1)
    assert w2["items"][-1]["name"] == DESCRIBED_ITEM["name"]


# ── Never raises ─────────────────────────────────────────────────────────────

def test_does_not_raise_on_empty_item():
    try:
        add_to_wardrobe({}, EMPTY_WARDROBE)
    except Exception as e:
        raise AssertionError(f"Expected no exception, got {type(e).__name__}: {e}")


def test_does_not_raise_on_missing_items_key_in_wardrobe():
    try:
        add_to_wardrobe(LISTING_ITEM, {})
    except Exception as e:
        raise AssertionError(f"Expected no exception, got {type(e).__name__}: {e}")
