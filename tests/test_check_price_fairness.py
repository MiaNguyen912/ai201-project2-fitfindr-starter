"""
Tests for check_price_fairness.

search_listings is mocked to give precise control over comparables.
Missing-price and empty-item tests need no mock.
"""

from unittest.mock import patch

from tools import check_price_fairness


# ── Fixtures ──────────────────────────────────────────────────────────────────

ITEM = {
    "id": "lst_test",
    "title": "Vintage Tee",
    "category": "tops",
    "style_tags": ["vintage", "graphic tee"],
    "condition": "good",
    "price": 20.0,
    "platform": "depop",
}


def _make_comparables(prices, category="tops", condition="good"):
    """Build fake listing dicts that pass the category + condition filter."""
    return [
        {
            "id": f"comp_{i}",
            "title": f"Comparable {i}",
            "category": category,
            "condition": condition,
            "price": float(p),
            "style_tags": [],
            "colors": [],
            "brand": None,
            "platform": "depop",
        }
        for i, p in enumerate(prices)
    ]


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_dict_on_normal_path():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    assert isinstance(result, dict)


def test_returns_string_on_missing_price_key():
    item = {k: v for k, v in ITEM.items() if k != "price"}
    assert isinstance(check_price_fairness(item), str)


def test_returns_string_on_none_price():
    assert isinstance(check_price_fairness({**ITEM, "price": None}), str)


def test_result_dict_has_all_required_keys():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    required = {"verdict", "item_price", "comparable_count", "median_price", "price_range", "explanation"}
    assert required.issubset(result.keys())


# ── Missing price guard ───────────────────────────────────────────────────────

def test_missing_price_error_string_is_descriptive():
    result = check_price_fairness({**ITEM, "price": None})
    assert "error" in result.lower() or "missing" in result.lower()


def test_missing_price_does_not_call_search_listings():
    with patch("tools.search_listings") as mock_sl:
        check_price_fairness({**ITEM, "price": None})
    mock_sl.assert_not_called()


# ── Insufficient data ─────────────────────────────────────────────────────────

def test_zero_comparables_verdict_is_insufficient_data():
    with patch("tools.search_listings", return_value=[]):
        result = check_price_fairness(ITEM)
    assert result["verdict"] == "insufficient data"


def test_one_comparable_verdict_is_insufficient_data():
    with patch("tools.search_listings", return_value=_make_comparables([20])):
        result = check_price_fairness(ITEM)
    assert result["verdict"] == "insufficient data"


def test_insufficient_data_median_price_is_none():
    with patch("tools.search_listings", return_value=[]):
        result = check_price_fairness(ITEM)
    assert result["median_price"] is None


def test_insufficient_data_price_range_is_none():
    with patch("tools.search_listings", return_value=[]):
        result = check_price_fairness(ITEM)
    assert result["price_range"] is None


def test_insufficient_data_still_echoes_item_price():
    with patch("tools.search_listings", return_value=[]):
        result = check_price_fairness(ITEM)
    assert result["item_price"] == ITEM["price"]


def test_insufficient_data_explanation_is_non_empty():
    with patch("tools.search_listings", return_value=[]):
        result = check_price_fairness(ITEM)
    assert isinstance(result["explanation"], str) and result["explanation"]


# ── Verdict thresholds ────────────────────────────────────────────────────────

def test_good_deal_when_price_is_80_percent_of_median():
    # Median of [18, 20, 22] = 20. Item price = 16 (80%) → good deal
    item = {**ITEM, "price": 16.0}
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(item)
    assert result["verdict"] == "good deal"


def test_fair_when_price_equals_median():
    # Item price == median → fair
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    assert result["verdict"] == "fair"


def test_fair_when_price_is_110_percent_of_median():
    # Median = 20, item price = 22 (110%) → still fair
    item = {**ITEM, "price": 22.0}
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(item)
    assert result["verdict"] == "fair"


def test_overpriced_when_price_is_125_percent_of_median():
    # Median = 20, item price = 25 (125%) → overpriced
    item = {**ITEM, "price": 25.0}
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(item)
    assert result["verdict"] == "overpriced"


# ── Field values ──────────────────────────────────────────────────────────────

def test_item_price_echoed_correctly():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    assert result["item_price"] == ITEM["price"]


def test_comparable_count_matches_number_of_valid_candidates():
    with patch("tools.search_listings", return_value=_make_comparables([15, 18, 20, 22, 25])):
        result = check_price_fairness(ITEM)
    assert result["comparable_count"] == 5


def test_median_price_computed_correctly():
    # [15, 20, 25] → median = 20
    with patch("tools.search_listings", return_value=_make_comparables([15, 20, 25])):
        result = check_price_fairness(ITEM)
    assert result["median_price"] == 20.0


def test_price_range_is_min_max():
    with patch("tools.search_listings", return_value=_make_comparables([15, 20, 25])):
        result = check_price_fairness(ITEM)
    assert result["price_range"] == (15.0, 25.0)


def test_explanation_is_non_empty_string():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    assert isinstance(result["explanation"], str) and result["explanation"]


def test_explanation_contains_verdict():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    assert result["verdict"] in result["explanation"]


def test_explanation_mentions_item_price():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM)
    assert str(int(ITEM["price"])) in result["explanation"]


# ── Candidate filtering ───────────────────────────────────────────────────────

def test_item_itself_excluded_by_id():
    # One candidate shares the item's id — must not count
    same_id_item = {**_make_comparables([20])[0], "id": ITEM["id"]}
    others = _make_comparables([18, 22])
    with patch("tools.search_listings", return_value=[same_id_item] + others):
        result = check_price_fairness(ITEM)
    assert result["comparable_count"] == 2


def test_different_category_excluded():
    wrong_cat = _make_comparables([20], category="shoes")
    same_cat = _make_comparables([18, 22])
    with patch("tools.search_listings", return_value=wrong_cat + same_cat):
        result = check_price_fairness(ITEM)
    assert result["comparable_count"] == 2


def test_adjacent_condition_included():
    # item condition = "good" (rank 1); "excellent" (rank 2) is 1 step away → included
    adj = _make_comparables([18], condition="excellent")
    same = _make_comparables([22], condition="good")
    with patch("tools.search_listings", return_value=adj + same):
        result = check_price_fairness(ITEM)
    assert result["comparable_count"] == 2


def test_candidate_with_no_price_excluded():
    no_price = {**_make_comparables([20])[0]}
    del no_price["price"]
    others = _make_comparables([18, 22])
    with patch("tools.search_listings", return_value=[no_price] + others):
        result = check_price_fairness(ITEM)
    assert result["comparable_count"] == 2


# ── max_comparables cap ───────────────────────────────────────────────────────

def test_max_comparables_caps_count():
    many = _make_comparables(range(1, 21))  # 20 items
    with patch("tools.search_listings", return_value=many):
        result = check_price_fairness(ITEM, max_comparables=5)
    assert result["comparable_count"] == 5


def test_max_comparables_1_triggers_insufficient_data():
    with patch("tools.search_listings", return_value=_make_comparables([18, 20, 22])):
        result = check_price_fairness(ITEM, max_comparables=1)
    assert result["verdict"] == "insufficient data"


# ── Never raises ──────────────────────────────────────────────────────────────

def test_does_not_raise_on_empty_item_dict():
    try:
        check_price_fairness({})
    except Exception as e:
        raise AssertionError(f"Expected no exception, got {type(e).__name__}: {e}")


def test_does_not_raise_on_missing_style_tags():
    item = {k: v for k, v in ITEM.items() if k != "style_tags"}
    try:
        with patch("tools.search_listings", return_value=_make_comparables([18, 20])):
            check_price_fairness(item)
    except Exception as e:
        raise AssertionError(f"Expected no exception, got {type(e).__name__}: {e}")


def test_does_not_raise_on_missing_category():
    item = {k: v for k, v in ITEM.items() if k != "category"}
    try:
        with patch("tools.search_listings", return_value=[]):
            check_price_fairness(item)
    except Exception as e:
        raise AssertionError(f"Expected no exception, got {type(e).__name__}: {e}")
