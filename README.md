
# FitFindr — Starter Kit

A multi-tool AI agent that searches secondhand clothing listings, evaluates price fairness, suggests outfits, and generates a shareable fit card — all in a single pass from a natural-language query.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup and Run

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

```bash
python app.py        # opens Gradio UI at http://localhost:7860
python agent.py      # CLI smoke test (happy path + no-results path)
```


## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.


---

## Tool Inventory

### Tool 1 — `search_listings`
**Purpose:** keyword search over `data/listings.json`, with optional size and price filters.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | free-text keywords describing the item |
| `size` | `str \| None` | size filter; `None` skips filtering |
| `max_price` | `float \| None` | price ceiling (inclusive); `None` skips filtering |

**Returns:** `list[dict]` of matching listings sorted by keyword-overlap score (best first), or `[]` if nothing matches. Each dict has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

---

### Tool 2 — `suggest_outfit`
**Purpose:** asks the LLM to style a thrifted item with the user's wardrobe.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | listing dict for the item being considered |
| `wardrobe` | `dict` | `{"items": [...]}` — user's closet; may be empty |

**Returns:** `str` — 1–2 outfit suggestions naming specific wardrobe pieces. Falls back to general styling advice when the wardrobe is empty; always returns a non-empty string.

---

### Tool 3 — `create_fit_card`
**Purpose:** generates a 2–4 sentence Instagram/TikTok OOTD caption.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | outfit suggestion from `suggest_outfit` |
| `new_item` | `dict` | listing dict (for title, price, platform) |
| `price_evaluation` | `dict \| None` | verdict dict from `check_price_fairness`; optional |

**Returns:** `str` caption mentioning item, price, and platform once each. Weaves in a pricing note when verdict is `"good deal"` or `"overpriced"`. Returns `"Error: ..."` string (never raises) if `outfit` is empty.

---

### Tool 4 — `add_to_wardrobe`
**Purpose:** appends a listing or user-described item to the wardrobe dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `item` | `dict` | listing dict or wardrobe-shaped dict to add |
| `wardrobe` | `dict` | current wardrobe to append to |

**Returns:** `tuple[dict, str]` — updated wardrobe and a confirmation (or error) message. Leaves wardrobe unchanged on missing `name`/`category` or duplicate `id`.

---

### Tool 5 — `check_price_fairness`
**Purpose:** compares an item's price against comparable listings to produce a fairness verdict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `item` | `dict` | listing dict to evaluate |
| `max_comparables` | `int` | cap on comparables used (default 10) |

**Returns:** `dict` with keys `verdict` (`"good deal"` / `"fair"` / `"overpriced"` / `"insufficient data"`), `item_price`, `comparable_count`, `median_price`, `price_range`, `explanation`. Returns an error string (not a dict) if `item["price"]` is missing.

---

## Planning Loop

The loop is **state-driven**: after each tool call it inspects the session dict and picks the next step based on which output fields are still empty. No field is written twice; no tool runs before its inputs exist.

```
parse query → [while not done]:
  1. search_results empty?    → call search_listings (with retry ladder)
  2. selected_item is None?   → pick search_results[0]
  3. price_evaluation empty?  → call check_price_fairness (non-blocking)
  4. outfit_suggestion None?  → call suggest_outfit
  4b. save_to_wardrobe=True?  → call add_to_wardrobe(selected_item, wardrobe)
                                 write result back to session["wardrobe"]
  5. fit_card is None?        → call create_fit_card → done = True
```

**Retry ladder (step 1):** when `search_listings` returns `[]`, the agent re-tries in order — drop size filter → relax price by +20% → keyword-only with no filters — stopping at the first non-empty result and recording the adjustment in `session["adjustment_note"]`. Only if every fallback is still empty does it set `session["error"]` and exit.

The loop terminates when either `session["fit_card"]` is set (success) or `session["error"]` is set (early exit).

---

## State Management

All state lives in a single `session` dict created by `_new_session()` at the start of each run. Tools do not call each other; the planning loop reads a tool's output from the session and passes it to the next tool as an argument.

| Field | Written by | Read by |
|-------|-----------|---------|
| `query` | startup | — |
| `parsed` | `_parse_query` | `search_listings` |
| `search_results` | `search_listings` | item selection |
| `adjustment_note` | retry ladder | `app.py` display |
| `selected_item` | item selection | `suggest_outfit`, `create_fit_card`, `check_price_fairness` |
| `price_evaluation` | `check_price_fairness` | `create_fit_card`, display |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | final output |
| `wardrobe` | startup; updated by `add_to_wardrobe` when `save_to_wardrobe=True` | `suggest_outfit` |
| `error` | any step on failure | planning loop / display |

The key handoff object is `selected_item`: because `search_listings` returns full listing dicts, the same dict flows unchanged into every downstream tool without any reshaping.

---

## Error Handling

| Tool | Failure mode | Agent response | Concrete example |
|------|-------------|----------------|-----------------|
| `search_listings` | No matches after all retries | Set `session["error"]`; skip moving forward with other tools like `suggest_outfit` and `create_fit_card` | for query `"designer ballgown size XXS under $5"`, `search_listings` can't find anything related in the first run -> it drops size, then relaxes price, then tries keyword-only to expand search range, but all return `[]` -> it sets `session["error"]` and print out error message: `"No listings matched — try a different style or keyword."` |
| `suggest_outfit` | Wardrobe is empty | Return general styling advice; loop continues to `create_fit_card` | Selecting "Empty wardrobe (new user)" in the UI still produces an outfit suggestion like "pair with wide-leg trousers and chunky boots for a streetwear look" |
| `suggest_outfit` | LLM call fails | Set `session["error"] = "Styling unavailable right now"` | Happens if `GROQ_API_KEY` is missing; agent stops before `create_fit_card` |
| `create_fit_card` | `outfit` is empty or whitespace | Return `"Error: ..."` string without calling LLM; agent sets `session["error"]` | `create_fit_card("", item)` returns `"Error: outfit suggestion is missing…"` immediately |
| `check_price_fairness` | Fewer than 2 comparable listings | Return `verdict = "insufficient data"`; loop continues (non-blocking) | Querying a niche item like `"rare pin"` with unique tags finds 0 comparables → `"insufficient data"` verdict, no price note in fit card |
| `check_price_fairness` | `item["price"]` missing | Return descriptive error string (not a dict); agent can surface it | `check_price_fairness({"id": "x", "category": "tops"})` → `"Error: item is missing a 'price' field…"` |
| `add_to_wardrobe` | Missing `name`/`category` or duplicate `id` | Return original wardrobe unchanged + error message; non-fatal | `add_to_wardrobe({"category": "tops"}, wardrobe)` → `"Error: item is missing a 'name'…"` |

---

## Spec Reflection

**What matched the plan:**
- The five-step state-driven loop matches the Technical Spec pseudocode exactly.
- Every tool degrades gracefully (no raises, error strings instead).
- `check_price_fairness` is non-blocking; `"insufficient data"` does not stop the loop.

**What changed during implementation:**
- **`_parse_query` grew significantly.** The spec described regex extraction in one sentence; the implementation needed five separate pattern tiers (explicit `size` keyword → W/L → one-size → slash sizes → letter sizes) to handle real query formats like `"size W30 L30"`, `"M/L"`, and `"size 8"`.
- **Stop words added to `search_listings`.** The spec didn't mention this; testing showed filler words like `"looking"`, `"for"`, `"in"` inflated scores on irrelevant listings, so a `_STOP_WORDS` set was added to the keyword tokenizer.
- **`_size_matches` helper added.** The spec described size filtering as a substring check (`"M" in "S/M"`). That broke for `"XL (fits oversized)"` and `"One Size (adjustable)"`, so a dedicated helper with parenthetical stripping and one-size normalization replaced it.
- **`session["adjustment_note"]` added.** The spec mentioned surfacing a note to the user when constraints were loosened; the field wasn't in the original schema but was added to carry that message through to `app.py`.
- `price_evaluation` flows through as a third argument to `create_fit_card`.
- **`create_fit_card` price note updated.** The spec said "weave in" the verdict naturally; the initial prompt said "pricier side" for overpriced (which a test caught as not containing the word "overpriced"), so the prompt was tightened to use the exact verdict word.

---

## AI Usage Example

### Implementing `run_agent()` in `agent.py`

**What I gave Claude:**
- The "Planning Loop — Technical Spec" pseudocode block from `planning.md`
- The "State Management" table from `planning.md`
- The "Architecture" diagram
- The existing `_new_session()` skeleton and the `run_agent` TODO docstring from `agent.py`

**What Claude produced:**
A complete `run_agent` implementation with the five-step while loop, local `done` flag, retry ladder with three fallbacks, and all session field guards. It also added `_parse_query` with basic regex for size and price, and `import re`.

**What I changed:**
- The initial `_parse_query` only handled plain letter sizes (`r'\b(XXS|XS|XXL|XL|[SMLX]{1,3})\b'`). I extended it to four additional size tiers (explicit `"size"` keyword, W/L, one-size/OS, slash sizes) to match real listing formats in the dataset.
- I added the `session["adjustment_note"]` field (not in the original schema) and wired it into the retry ladder so `app.py` could display what constraint was loosened.

---

### Updating `create_fit_card` to accept `price_evaluation`

Initially, the signature of `create_fit_card` was `create_fit_card(outfit: str, new_item: dict)`. However, I wanted the returned result of `price_evaluation` to be used in creating the fit card, because price evaluation detail can influence how user like the listing. Therfore, i used Claude to add a new input field to `create_fit_card`

**What I gave Claude:**
- The updated Tool 3 description from `planning.md` (which I had already rewritten to name `price_evaluation` as a third input)
- The existing `create_fit_card` body in `tools.py` (two-argument version)
- The instruction: add `price_evaluation: dict | None = None` and weave in a price note for `"good deal"` / `"overpriced"` verdicts

**What Claude produced:**
Updated signature, docstring, and a `price_note` block that injected one line into the prompt based on the verdict. The "overpriced" note said `"on the pricier side"`.

**What I changed:**
- The test `assert "overpriced" in _captured_prompt(mock_client)` failed because the prompt used "pricier side" rather than the word "overpriced". I changed the note to `"This item is overpriced vs. similar listings"` so the exact verdict word appears in the prompt and the test passes.
- I also added two more `elif` branches — for `"fair"` and `"insufficient data"` — so the prompt explicitly tells the LLM to skip the price note in those cases, rather than leaving it ambiguous.
