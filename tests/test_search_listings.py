from tools import search_listings


#################################################### test search_listings ##################################################

# ── Basic functionality ───

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

# ── Price boundary ────

def test_price_filter_inclusive_boundary():
    # lst_002 "Y2K Baby Tee" costs exactly $18 — must be included at max_price=18
    results = search_listings("baby tee", size=None, max_price=18)
    assert any(item["price"] == 18 for item in results)

def test_price_filter_excludes_above_ceiling():
    results = search_listings("jeans", size=None, max_price=20)
    assert all(item["price"] <= 20 for item in results)

def test_price_filter_none_returns_all_prices():
    results_no_filter = search_listings("vintage", size=None, max_price=None)
    results_low_cap = search_listings("vintage", size=None, max_price=5)
    assert len(results_no_filter) >= len(results_low_cap)

# ── Size filter ────

def test_size_filter_exact_match():
    results = search_listings("tee", size="S", max_price=None)
    for item in results:
        assert "s" in item["size"].lower()

def test_size_filter_case_insensitive():
    results_upper = search_listings("tee", size="M", max_price=None)
    results_lower = search_listings("tee", size="m", max_price=None)
    assert results_upper == results_lower

def test_size_filter_substring_match():
    # "m" should match sizes like "S/M" and "M/L" as well as plain "M"
    results = search_listings("shirt", size="m", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()

def test_size_filter_no_match_returns_empty():
    results = search_listings("pants", size="XXXS", max_price=None)
    assert results == []

# ── Scoring & ranking ─────

def test_results_sorted_by_relevance():
    # A query with many keywords should rank higher-overlap items first.
    results = search_listings("vintage graphic tee streetwear", size=None, max_price=None)
    assert len(results) >= 2
    # Verify descending score order by checking no result ranks below a later one
    # (we can't inspect scores directly, so we re-score ourselves)
    import re
    keywords = set(re.findall(r"[a-z0-9]+", "vintage graphic tee streetwear"))
    keywords = {k for k in keywords if len(k) >= 2}

    def score(item):
        haystack = " ".join([
            item.get("title", ""), item.get("description", ""),
            item.get("category", ""),
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
            item.get("brand") or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in haystack)

    scores = [score(r) for r in results]
    assert scores == sorted(scores, reverse=True)

def test_zero_score_items_excluded():
    # A very specific nonsense query should return nothing, not zero-scored items
    results = search_listings("xyzzy qqqq", size=None, max_price=None)
    assert results == []

# ── Description edge cases ─────

def test_empty_description_returns_empty():
    # No keywords → every listing scores 0 → empty result
    results = search_listings("", size=None, max_price=None)
    assert results == []

def test_single_char_description_returns_empty():
    # Single-char tokens are filtered (len >= 2 required)
    results = search_listings("t", size=None, max_price=None)
    assert results == []

def test_description_keyword_matching_is_case_insensitive():
    results_lower = search_listings("vintage", size=None, max_price=None)
    results_upper = search_listings("VINTAGE", size=None, max_price=None)
    assert results_lower == results_upper

# ── Return type & structure ──────

def test_return_type_is_list_of_dicts():
    results = search_listings("vintage", size=None, max_price=None)
    assert isinstance(results, list)
    assert all(isinstance(item, dict) for item in results)

def test_result_dicts_have_expected_fields():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) > 0
    required_fields = {"id", "title", "description", "category", "style_tags", "size", "condition", "price", "colors", "brand", "platform"}
    for item in results:
        assert required_fields.issubset(item.keys())


# ── Combined filters ───────

def test_combined_size_and_price_filter():
    results = search_listings("top", size="M", max_price=30)
    for item in results:
        assert item["price"] <= 30
        assert "m" in item["size"].lower()

def test_all_filters_none_returns_keyword_matches():
    results = search_listings("flannel", size=None, max_price=None)
    assert len(results) > 0
    assert all(isinstance(item, dict) for item in results)
