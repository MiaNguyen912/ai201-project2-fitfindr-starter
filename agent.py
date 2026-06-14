"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card, add_to_wardrobe, check_price_fairness


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract structured parameters from a natural-language query.

    Returns a dict with keys:
        description: str | None  — everything that isn't a size or price token
        size:        str | None  — e.g. "XS", "S", "M", "L", "XL", "XXL"
        max_price:   float | None — numeric value from "under $30" / "< $30" / "$30 max"
    """
    text = query.strip()

    # --- size (tried in order of specificity) ---
    size = None
    size_match = None

    # 0. Explicit "size <value>" — highest priority, also strips the keyword
    #    Covers: "size M", "size M/L", "size W30 L30", "size 8" (numeric/shoes)
    size_kw = re.search(
        r'\bsize\s+'
        r'(W\d+[/\s]L?\d+|(?:XXS|XXL|XS|XL|[SML])(?:/(?:XXS|XXL|XS|XL|[SML]))?|\d+)',
        text, re.IGNORECASE,
    )
    if size_kw:
        raw = size_kw.group(1).strip()
        wl_kw = re.match(r'W(\d+)[/\s]L?(\d+)', raw, re.IGNORECASE)
        if wl_kw:
            size = f"W{wl_kw.group(1)} L{wl_kw.group(2)}"
        elif re.match(r'\d+$', raw):
            size = raw          # numeric size (e.g. shoe size 8)
        else:
            size = raw.upper().replace(' ', '')
        size_match = size_kw

    if size is None:
        # W30 L30 / W30/L30 (waist + inseam for jeans) without "size" keyword
        wl = re.search(r'\bW(\d+)[/\s]L?(\d+)\b', text, re.IGNORECASE)
        if wl:
            size = f"W{wl.group(1)} L{wl.group(2)}"
            size_match = wl

    if size is None:
        # One Size / OS
        os_m = re.search(r'\bone\s+size\b|\bOS\b', text, re.IGNORECASE)
        if os_m:
            size = "one size"
            size_match = os_m

    if size is None:
        # Slash sizes without the "size" keyword: S/M, M/L, L/XL, XS/S, XL/XXL
        slash = re.search(
            r'\b(XXS|XXL|XS|XL|[SML])\s*/\s*(XXS|XXL|XS|XL|[SML])\b',
            text, re.IGNORECASE,
        )
        if slash:
            size = slash.group(0).upper().replace(' ', '')
            size_match = slash

    if size is None:
        # Standard letter sizes (longer alternatives first to avoid partial matches)
        letter = re.search(r'\b(XXS|XXL|XS|XL|[SML])\b', text, re.IGNORECASE)
        if letter:
            size = letter.group(0).upper()
            size_match = letter

    # --- max price ---
    price_match = re.search(
        r'(?:under|below|<|max|up\s+to)?\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars?|usd|max)?',
        text,
        re.IGNORECASE,
    )
    max_price = float(price_match.group(1)) if price_match else None

    # --- description: strip size and price tokens from the original text ---
    desc = text
    if size_match:
        desc = desc[:size_match.start()] + desc[size_match.end():]
    if price_match:
        desc = desc[:price_match.start()] + desc[price_match.end():]
    # clean up leftover punctuation / filler words
    desc = re.sub(r'\b(under|below|max|up to|size|for|a|an|the)\b', ' ', desc, flags=re.IGNORECASE)
    desc = re.sub(r'[,$<]', ' ', desc)
    desc = re.sub(r'\s+', ' ', desc).strip(' ,.-')

    return {
        "description": desc or None,
        "size": size,
        "max_price": max_price,
    }



# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "adjustment_note": None,      # optional free-form string on how we adjusted the search (e.g., loosened price constraint)
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "price_evaluation": {},      # dict returned by check_price_fairness
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }

# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict, save_to_wardrobe: bool = False) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into structured parameters
    parsed = _parse_query(query)
    print(f"DEBUG: parsed query into description='{parsed['description']}', size='{parsed['size']}', max_price={parsed['max_price']}")
    session["parsed"] = {
        "description": parsed["description"] or query,
        "size": parsed["size"],
        "max_price": parsed["max_price"],
    }

    done = False
    while not done:
        # Step 3: search (retry ladder)
        if not session["search_results"]:
            desc = session["parsed"]["description"]
            size = session["parsed"]["size"]
            max_price = session["parsed"]["max_price"]

            results = search_listings(desc, size, max_price)
            if not results and size:
                results = search_listings(desc, None, max_price)
                session["adjustment_note"] = "Cannot find items matching the size filter, so I removed the size constraint to broaden the search."
                print("DEBUG: no results with size filter, retrying without size")
            if not results and max_price is not None:
                loosened = round(max_price * 1.20, 2)
                results = search_listings(desc, size, loosened)
                session["adjustment_note"] = "Cannot find items matching the price filter, so I increased the max price by 20% to broaden the search."
                print("DEBUG: no results with price filter, retrying with loosened price")
            if not results:
                results = search_listings(desc, None, None)
                session["adjustment_note"] = "Cannot find items matching the filters, so I removed all constraints to broaden the search."
                print("DEBUG: no results with any filters, retrying without constraints")
            if not results:
                session["error"] = "No listings matched — try a different style or keyword."
                print("DEBUG: no results even after loosening filters")
                done = True
                continue
            session["search_results"] = results
            continue

        # Step 4: auto-select top result
        if session["selected_item"] is None:
            session["selected_item"] = session["search_results"][0]
            continue

        # Step 5: price check (non-blocking — runs after item is selected)
        if not session["price_evaluation"]:
            session["price_evaluation"] = check_price_fairness(session["selected_item"])
            continue

        # Step 6: outfit suggestion
        if session["outfit_suggestion"] is None:
            outfit = suggest_outfit(session["selected_item"], session["wardrobe"])
            if not outfit:
                session["error"] = "Styling unavailable right now — please try again."
                done = True
                continue
            session["outfit_suggestion"] = outfit
            continue

        # add to custom wardrobe (only when user opted in)
        if save_to_wardrobe:
            updated_wardrobe, _ = add_to_wardrobe(session["selected_item"], session["wardrobe"], persist=True)
            session["wardrobe"] = updated_wardrobe            
            
        # Step 7: create fit card (terminal step)
        if session["fit_card"] is None:
            card = create_fit_card(
                session["outfit_suggestion"],
                session["selected_item"],
                session["price_evaluation"],
            )
            if card.startswith("Error:"):
                session["error"] = card
            else:
                session["fit_card"] = card
            done = True
            continue

    print(f"DEBUG: final session state: {session}")
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
