# Cooking learning path

A progressive path of 12 basic techniques, plus the two rubrics agents use to score recipes.
Mostly practical know-how: claims are [OPINION] (culinary practice) unless labelled otherwise.

## The path

Do them roughly in order; each step reuses earlier ones. One technique per week is plenty.

| # | Technique | What it teaches | Practice dish |
|---|---|---|---|
| 1 | **Knife basics** — claw grip, rocking cut, dicing an onion | Safety, speed, even pieces cook evenly | Simple tomato-cucumber salad |
| 2 | **Rice and pasta** — salted boiling water for pasta; rice by ratio or absorption | Timing, doneness, ratios | Pasta with jarred tomato sauce + frozen peas |
| 3 | **Sautéing onions** — medium heat, oil, patience: soft (5 min) → golden (15 min) | Heat control, building flavour bases | Onion-garlic base for a lentil sauce |
| 4 | **Eggs** — scrambled (low heat), boiled (timed), fried | Gentle heat, timing, protein setting | Scrambled eggs on whole-grain toast |
| 5 | **Roasting vegetables** — 200–220 °C, oil, spread out, don't crowd | Browning (Maillard), oven use | Roasted carrots, peppers, chickpeas |
| 6 | **Searing meat / tofu** — dry surface, hot pan, don't move it too early | High heat, resting, food safety (poultry cooked through) | Chicken breast or tofu with pan sauce |
| 7 | **Legumes** — canned (rinse) and dried (soak, simmer); red lentils need no soak | Cheap protein and fibre, simmering | Red-lentil dal |
| 8 | **Seasoning and tasting** — salt in stages, acid (lemon/vinegar) at the end, taste every step | Adjusting a dish instead of following blindly | Adjust a bland soup until it "pops" |
| 9 | **Sauces and emulsions** — pan sauce, yogurt sauce, vinaigrette, simple roux | Emulsifying, thickening, balancing fat/acid | Vinaigrette + béchamel for a gratin |
| 10 | **Oven trays (sheet-pan meals)** — protein + vegetables + starch on one tray, timed by size | Planning cooking times, low washing-up | Salmon or tofu, potatoes, broccoli tray |
| 11 | **One-pot / Thermomix-style cooking** — sauté, simmer and finish in one vessel or device | Sequencing ingredients, device settings | One-pot chili or risotto (device or pot) |
| 12 | **Batch cooking** — cook 3–4 portions, cool quickly, fridge 3–4 days / freeze | Planning, storage safety, meal-prep habits | Big pot of chili → 2 dinners + 2 frozen |

Food-safety notes inside the path: cool cooked food fast and refrigerate within 2 h; poultry and
minced meat cooked through (core ≥ 70 °C for ≥ 2 min); reheat until steaming hot. [STRONG] (1, 2)

## Rubric: simplicity (`simplicity`, 1–5, higher = easier)

Score each criterion, then take the **lowest** value (the hardest part decides).
"Active time" = hands-on work; unattended simmering or oven time does not count.

| Score | Active time | Ingredients (excl. salt, pepper, oil, water) | Vessels/devices | Technique |
|---|---|---|---|---|
| **5** | ≤ 15 min | ≤ 5 | 1 (pot, tray, or one-pot device) | chopping, stirring, assembling; hard to fail |
| **4** | ≤ 25 min | ≤ 8 | ≤ 2 | one basic technique from steps 1–7 |
| **3** | ≤ 40 min | ≤ 12 | ≤ 3 | coordinating 2–3 components, or one sensitive step (searing, roux) |
| **2** | ≤ 60 min | ≤ 15 | ≤ 4 | sensitive timing or emulsion, dough, several parallel components |
| **1** | > 60 min | > 15 | > 4 | multi-stage or precision technique (fresh pasta, laminated dough) |

Example: sheet-pan salmon with potatoes and broccoli — 15 min active, 4 ingredients, 1 tray,
basic technique → **5**. Risotto in a pot — 30 min stirring → **3**; in a Thermomix → **4–5**.

## Rubric: nutrition (`nutrition_score`, 1–5, per serving)

Add points, round to the nearest whole number, minimum 1, maximum 5.

| Criterion | Points | Basis |
|---|---|---|
| Protein ≥ 25 g (≥ 15 g → 0.5) | 1 | Supports muscle gain targets (3) [STRONG] |
| Vegetables/legumes/fruit ≥ 150 g (≥ 75 g → 0.5) | 1 | DGE: ≥ 5 portions a day, ~¾ of food plant-based (4) [STRONG] |
| Whole grain, potato with skin, or legume-based carbs — or ≥ 8 g fibre | 1 | DGE whole-grain advice (4) [STRONG] |
| Fat mostly unsaturated (rapeseed/olive oil, nuts, fish); little butter, cream, fatty or processed meat | 1 | (4, 5) [STRONG] |
| Salt ≤ 1.7 g (≈ ⅓ of WHO's < 5 g/day), no or little processed meat | 1 | (5, 6) [STRONG] |

- Compute protein from `bos food calc`; estimate grams of vegetables from the recipe.
- **Do not deduct for calories.** For users aiming to gain weight, energy-dense healthy foods
  (nuts, oil, whole milk) are fine; mention calories separately. [OPINION]
- Score the dish as served, including obvious sides (bread, rice).

Example: red-lentil dal with brown rice and spinach — protein ~22 g (0.5), vegetables + legumes
> 150 g (1), whole grain + legumes (1), rapeseed oil (1), salt ~1.5 g (1) → 4.5 → **5**
(round half up). Pasta with cream and bacon → about **1–2**.

## How body-os uses this

- **Tracked:** cookbook entries with `simplicity`, `nutrition_score`, `skill` (technique learned),
  rating 👍/👎; which path steps are done.
- **Agent behaviour:** the "ambitious" suggestion carries a learning note from the next unfinished
  step; scores always follow the two rubrics above, so they are comparable across weeks.
- **Weekly review question:** "Did I cook at least a few times, learn one new technique, and how
  did average nutrition score and protein per meal look?"

## Not medical advice — see a doctor if …

- food allergies or intolerances are suspected (hives, swelling, breathing trouble = emergency);
- you have a condition needing a special diet (kidney disease, diabetes, coeliac disease) —
  the nutrition rubric is general and not a medical diet.

## Sources

1. BfR — protection against foodborne infections in private households (hygiene, core temperatures): https://www.bfr.bund.de/cm/350/verbrauchertipps_schutz_vor_lebensmittelinfektionen_im_privathaushalt.pdf
2. USDA FoodSafety.gov — cold food storage and leftovers: https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts
3. Morton et al. 2018, BJSM — protein and resistance training meta-analysis: https://pubmed.ncbi.nlm.nih.gov/28698222/
4. DGE — "Gut essen und trinken" food-based recommendations (2024): https://www.dge.de/gesunde-ernaehrung/gut-essen-und-trinken/dge-empfehlungen/
5. WHO healthy diet fact sheet (fats, salt): https://www.who.int/news-room/fact-sheets/detail/healthy-diet
6. WHO sodium reduction fact sheet (< 5 g salt/day): https://www.who.int/news-room/fact-sheets/detail/sodium-reduction
