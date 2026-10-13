# Module: nutrition

**Tracks:** meals (description, items, kcal, protein, carbs, fat, fibre), water, other drinks.
Knowledge: [../knowledge/energy-and-protein-for-muscle-gain.md](../knowledge/energy-and-protein-for-muscle-gain.md).

**Meal from a photo or text**
1. Identify components and estimate grams (plate ≈ 26 cm; use visible packaging, cutlery, hands).
2. Look up each item: `bos food search <name>` → choose the closest `food_id`; packaged products may
   use Open Food Facts values when available.
3. `bos food calc '[{"food_id": "...", "g": 120}, …]'` → store totals in the `meal` event with
   `items`, `src: "photo"`, `conf` (`med` typical, `low` for mixed dishes/restaurant food).
4. If the pantry module is active, add `pantry_used` for items that plausibly came from the pantry.
5. Reply with one line: dish, ≈ kcal, ≈ protein. Never ask per-item questions; ask one question only
   if the portion size is genuinely unclear and large.

**Settings:** `nutrition.show_numbers` (false → describe meals without kcal; see SAFETY.md §2),
`nutrition.targets` (kcal/protein ranges set at review time), `nutrition.sources`.

**Review:** daily kcal/protein means vs targets, protein distribution across meals, weight trend
as the ground truth (if weight rises/falls faster than intended, adjust targets, not the estimates).
