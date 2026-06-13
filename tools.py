"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from config import LLM_MODEL
from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description, optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering. Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns: A list of matching listing dicts, sorted by relevance (best match first). Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields: id, title, description, category, style_tags (list), size, condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Tokenize the description into lowercase keywords (length >= 2) used for scoring.
    keywords = [tok for tok in re.findall(r"[a-z0-9]+", description.lower()) if len(tok) >= 2]

    size_filter = size.lower().strip() if size else None

    results: list[tuple[int, dict]] = []
    for listing in listings:
        # Price filter (inclusive). Skip listings above the ceiling.
        if max_price is not None and listing.get("price", 0) > max_price:
            continue

        # Size filter: case-insensitive and substring-aware, so "m" matches "s/m".
        if size_filter is not None:
            listing_size = str(listing.get("size", "")).lower()
            if size_filter not in listing_size:
                continue

        # Score by keyword overlap against the listing's searchable text.
        haystack = " ".join(
            [
                str(listing.get("title", "")),
                str(listing.get("description", "")),
                str(listing.get("category", "")),
                " ".join(listing.get("style_tags", []) or []),
                " ".join(listing.get("colors", []) or []),
                str(listing.get("brand") or ""),
            ]
        ).lower()
        score = sum(1 for kw in set(keywords) if kw in haystack)

        # Drop listings with no keyword overlap.
        if score == 0:
            continue

        results.append((score, listing))

    # Sort by score, highest first. Stable sort preserves dataset order on ties.
    results.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.  If the wardrobe is empty, offer general styling advice for the item  rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask the LLM to suggest specific outfit combinations using the new item  and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    item_desc = (
        f"Title: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Colors: {', '.join(new_item.get('colors', []) or [])}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []) or [])}\n"
        f"Condition: {new_item.get('condition', 'unknown')}\n"
        f"Brand: {new_item.get('brand') or 'no brand listed'}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A user is considering buying this secondhand item:\n{item_desc}\n\n"
            "They don't have a wardrobe on file yet. Give them 1-2 outfit ideas using this item, "
            "describe what types of pieces pair well with it, what vibe or aesthetic it suits, "
            "and any small styling tips (tucking, layering, etc.). "
            "Be specific and casual, like a knowledgeable friend giving style advice. "
            "Keep it under 150 words."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {item['name']} ({item['category']}, "
            f"colors: {', '.join(item.get('colors', []))})"
            for item in wardrobe_items
        )
        prompt = (
            f"A user is considering buying this secondhand item:\n{item_desc}\n\n"
            f"Their current wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfits that pair the new item with specific named pieces "
            "from their wardrobe (use the exact names listed above, e.g. 'your baggy straight-leg jeans'). "
            "For each outfit note the vibe and one small styling tip (tuck, layer, cuff, etc.). "
            "Be casual and conversational, like a style-savvy friend. "
            "Keep it under 200 words."
        )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300,
    )

    result = response.choices[0].message.content.strip()
    # Guard: if the LLM somehow returns empty content, surface a safe fallback
    return result or "This piece is versatile — try pairing it with your go-to basics for an effortless everyday look."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns: A 2–4 sentence string usable as an Instagram/TikTok caption. If outfit is empty or missing, return a descriptive error message string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit, and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # To test this tool independently, run this cli:
        # python -c "
        # from tools import create_fit_card
        # item = {
        #     'title': 'Graphic Tee — 2003 Tour Bootleg Style',
        #     'price': 22.0,
        #     'platform': 'depop',
        #     'category': 'tops',
        #     'colors': ['black', 'white'],
        #     'style_tags': ['vintage', 'graphic tee', 'streetwear'],
        #     'condition': 'good',
        #     'brand': None,
        # }
        # outfit = 'Pair this faded bootleg tee with your baggy dark-wash jeans and chunky white sneakers for a classic 90s streetwear look. Tuck the front hem slightly for shape and layer your vintage black denim jacket on top when it gets cold.'
        # print(create_fit_card(outfit, item))
        # "

    if not outfit or not outfit.strip():
        return "Error: outfit suggestion is missing — run suggest_outfit first before generating a fit card."

    title = new_item.get("title", "this thrifted find")
    price = new_item.get("price")
    platform = new_item.get("platform", "a thrift platform")

    price_str = f"${price:.0f}" if price is not None else "a steal"

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok OOTD caption for a thrifted item.\n\n"
        f"Item: {title}\n"
        f"Price: {price_str}\n"
        f"Platform: {platform}\n"
        f"Outfit: {outfit.strip()}\n\n"
        "Rules:\n"
        "- Sound casual and authentic, like a real person posting their outfit, NOT a product description\n"
        "- Mention the item name, price, and platform each exactly once, woven in naturally\n"
        "- Capture the specific vibe of the outfit (don't be generic)\n"
        "- 2–4 sentences only; no hashtags, may add icons/emojis if it fits the vibe\n"
    )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.1,
        max_tokens=150,
    )

    result = response.choices[0].message.content.strip()
    return result or f"thrifted {title} off {platform} for {price_str} and honestly it just works."


# ── Tool 4: add_to_wardrobe ───────────────────────────────────────────────────

def add_to_wardrobe(item: dict, wardrobe: dict) -> tuple[dict, str]:
    """
    Add an item to the user's wardrobe, mapping it into the wardrobe item shape.

    The item can be either:
      (1) a listing dict from search_listings (uses 'title' as the name), or
      (2) a user-described item already in wardrobe shape (uses 'name' directly).

    Args:
        item: Dict to add. Required fields after mapping: 'name' and 'category'. Optional: 'id', 'colors', 'style_tags', 'notes'.
        wardrobe: Current wardrobe dict with an 'items' key (list of wardrobe items).

    Returns:
        A tuple of (wardrobe_dict, message_str).
        On success: updated wardrobe with the new item appended, and a confirmation string.
        On failure: original wardrobe unchanged, and a descriptive error string. Never raises an exception.
    """
    # to test this tool independently, run this cli:
        # python -c "
        # from tools import add_to_wardrobe

        # wardrobe = {'items': [
        #     {'id': 'w_001', 'name': 'Baggy straight-leg jeans', 'category': 'bottoms', 'colors': ['dark blue'], 'style_tags': ['denim']}
        # ]}

        # # Case 1: add a listing dict (title -> name mapping)
        # listing = {'id': 'lst_006', 'title': 'Graphic Tee — 2003 Tour Bootleg Style', 'category': 'tops', 'colors': ['black', 'white'], 'style_tags': ['vintage', 'streetwear'], 'price': 22.0, 'platform': 'depop'}
        # w, msg = add_to_wardrobe(listing, wardrobe)
        # print('Case 1 (listing dict):', msg)
        # print('  wardrobe size:', len(w['items']), '| new item name:', w['items'][-1]['name'])

        # # Case 2: duplicate id
        # w2, msg2 = add_to_wardrobe(listing, w)
        # print('Case 2 (duplicate):', msg2)
        # print('  wardrobe size unchanged:', len(w2['items']))

        # # Case 3: user-described item (name key, no id)
        # described = {'name': 'Black combat boots', 'category': 'shoes', 'colors': ['black'], 'style_tags': ['grunge', 'boots'], 'notes': 'Lace-up, mid-ankle'}
        # w3, msg3 = add_to_wardrobe(described, wardrobe)
        # print('Case 3 (described item):', msg3)
        # print('  auto id:', w3['items'][-1]['id'], '| notes:', w3['items'][-1].get('notes'))

        # # Case 4: missing name/title
        # w4, msg4 = add_to_wardrobe({'category': 'tops', 'colors': ['red']}, wardrobe)
        # print('Case 4 (missing name):', msg4)

        # # Case 5: missing category
        # w5, msg5 = add_to_wardrobe({'name': 'Mystery item'}, wardrobe)
        # print('Case 5 (missing category):', msg5)
        # "

    
    # Resolve name: wardrobe-described items use 'name'; listing dicts use 'title'.
    name = item.get("name") or item.get("title")
    category = item.get("category")

    if not name:
        return wardrobe, "Error: item is missing a 'name' (or 'title') — wardrobe unchanged."
    if not category:
        return wardrobe, "Error: item is missing a 'category' — wardrobe unchanged."

    items = wardrobe.get("items", [])

    # Generate a stable id if the item doesn't have one.
    item_id = item.get("id") or f"w_custom_{len(items) + 1:03d}"

    # Duplicate check by id.
    if any(w["id"] == item_id for w in items):
        return wardrobe, f"'{name}' (id: {item_id}) is already in your wardrobe — skipping."

    wardrobe_item = {
        "id": item_id,
        "name": name,
        "category": category,
        "colors": list(item.get("colors") or []),
        "style_tags": list(item.get("style_tags") or []),
    }
    if item.get("notes"):
        wardrobe_item["notes"] = item["notes"]

    updated = {**wardrobe, "items": items + [wardrobe_item]}
    return updated, f"Added '{name}' to your wardrobe."
    
