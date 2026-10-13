# Module: pantry and cooking

**Tracks:** purchases, pantry stock with expiry, consumption, discards, cookbook with ratings.
Knowledge: [../knowledge/food-safety-and-expiry.md](../knowledge/food-safety-and-expiry.md),
[../knowledge/cooking-learning-path.md](../knowledge/cooking-learning-path.md).

## Purchase (receipt photo, grocery photo or text)

1. Extract every product: name, quantity/unit, price (receipt), store.
2. For each, without asking the user: category, storage (fridge/freezer/pantry), `date_kind`
   (`use_by` for raw meat/minced meat/fresh fish/poultry; `best_before` for most packaged food;
   `none` for loose produce/bread), `expires` — a printed date visible in the photo wins; otherwise
   estimate from typical shelf life (knowledge page table, web lookup if unsure) and set
   `expires_est: true`. Add a short `check_hint` for `best_before`/`none` items. Match a `food_id`
   when cheap to do.
3. Send **one summary** (table: product · qty · storage · expires (est.) · kcal/protein per 100 g
   where useful) and ask once: "Passt das so?" Corrections → fix, then store one `purchase` event.

## Upkeep

- Logged meals subtract via `pantry_used` (estimate).
- Weekly fridge/pantry photo → `adjust` events (present/gone/opened). Don't chase small uncertainties.
- Opening an item with a shorter opened life (milk, jars, cream) → `open` with new `expires`.
- `bos pantry` statuses: `soon` → mention in the first check-in of the day; `check` → tell the user
  what to inspect (`check_hint`) and until when it is typically still fine; `discard` (use-by passed
  or check grace exceeded) → tell the user to throw it away; log `discard` when confirmed.
- Never use `check`/`discard` items in suggestions.

## Cooking suggestions

On request ("was koche ich?") and proactively when items become `soon`.
- Default 4 options: ≥ 1 very simple (≤ 15 min active, few steps — prefer the one-pot device, e.g.
  Thermomix, when owned), 1–2 medium, 1 more ambitious with a **learning note** (technique).
- Rotate cuisines; prioritise pantry items by urgency; list missing ingredients.
- Each option shows: time, simplicity ★1–5, nutrition ★1–5 (rubrics in the cooking knowledge page),
  ≈ kcal and protein per serving (computed with `bos food calc`, not guessed), servings =
  `household.portions_default`.
- Device steps: write own instructions (e.g. Thermomix speed/time/temperature). Proprietary recipe
  platforms (Cookidoo etc.): mention a recipe **by name or link** only; never copy their text.
- After cooking: append to `recipes/cookbook.jsonl` (in `household/` in household mode) with `status: cooked`; ask 👍/👎 once and use
  ratings for future suggestions.

## Shopping list

On request and at the weekly review: stock + goals + 3–4 rough dish ideas → grouped list
(produce, dairy, protein, dry goods), noting what is already at home.

**Settings:** `household` (members, portions_default, shared dislikes with consent), `kitchen`
(devices, platforms), `pantry` (mode, store_prices), `cooking` (options, cuisines_recent).
