# Food safety and expiry dates

## Two different dates (EU and German law)

| Label | German | Meaning | Label |
|---|---|---|---|
| **Best before** | Mindesthaltbarkeitsdatum (MHD), "mindestens haltbar bis" | Quality guarantee if stored as stated. After it the food is **not automatically spoiled**; shops may even sell it if it is still fine. | [STRONG] (1, 2) |
| **Use by** | Verbrauchsdatum, "zu verbrauchen bis" | For highly perishable foods (minced meat, fresh poultry, fresh fish, pre-cut salad). After this date the food **counts as unsafe by law**; do not eat it, even if it looks and smells fine. | [STRONG] (1, 2) |

- Some foods need no MHD at all: fresh fruit and vegetables, sugar, salt, vinegar, wine and
  drinks ≥ 10 % alcohol, chewing gum; bakery bread usually has none. [STRONG] (2)
- **Once opened, the MHD no longer applies** — follow "after opening use within …" hints. [STRONG] (2)
- Pathogens like *Listeria* or *Salmonella* do not always change smell or look; that is why
  use-by foods are never "sniff-tested". [STRONG] (3)

## Checking MHD-expired food by category

Look → smell → small taste, in that order; stop at the first bad sign. [MODERATE] (2)

| Category | Usually fine past MHD if … | Bad signs |
|---|---|---|
| Yogurt, quark, skyr, hard cheese (unopened) | days to weeks; lid not bulging | sour/off smell beyond normal, mould, pink/yellow spots, fizzing |
| Milk (fresh / ESL) unopened | a few days; check before pouring | lumps, sour smell (pasteurised milk sours visibly) |
| UHT milk unopened | months | bulging pack, bitter taste |
| Eggs (DE: MHD ≤ 28 days after laying) | use only **fully cooked** after MHD (no tiramisu, soft eggs) | sulphur smell when cracked; floats in water = old |
| Bread / baked goods | stale ≠ unsafe; toast or use for crumbs | **any mould** → discard whole loaf / package |
| Dry goods (pasta, rice, flour, oats, lentils) | months to years if dry and closed | insects/webs, rancid smell (whole-grain flour, nuts, oats) |
| Cans and jars (unopened) | years; best before is about quality | bulging, leaking, deep dents on seams, rust, spurting on opening |
| Produce (no date) | judge by look and feel | slime, mould, fermented smell |
| Opened jars (jam, pesto, sauces) | see table below; fridge only | mould on surface, fizzing, off smell |

Sources: (2, 4, 5). Eggs rule: (6). Labels: [STRONG] for discard signs, [MODERATE] for
"usually fine" ranges.

## Typical storage times (good quality, fridge ≤ 4–7 °C, freezer −18 °C)

Approximate; printed dates win. Freezer times are about quality — food frozen at −18 °C stays
safe indefinitely. [STRONG] (4)

| Food | Fridge | Freezer | Pantry |
|---|---|---|---|
| Minced meat, raw | 1 day (use-by) | 3–4 months | — |
| Raw poultry | 1–2 days (use-by) | 9–12 months | — |
| Steaks, chops, raw | 3–5 days | 4–12 months | — |
| Fresh fish | 1–2 days (use-by) | lean 6 months, fatty 2–3 months | — |
| Sliced sausage / ham, opened | 3–5 days | 1–2 months | — |
| Cooked leftovers, soups, stews | 3–4 days | 2–3 months | — |
| Cooked rice | **cool fast, eat within 1 day** (max 2) | 1 month | never left warm |
| Fresh milk, opened | 2–4 days | 3 months (texture changes) | — |
| Yogurt / quark, opened | 3–5 days | not ideal | — |
| Hard cheese, opened piece | 3–4 weeks | 6 months (grate after) | — |
| Soft cheese (brie, mozzarella), opened | 2–7 days | not ideal | — |
| Butter | 1–3 months | 6–9 months | — |
| Eggs (raw, in shell) | up to MHD; cook fully after | yolk/white only, 12 months | DE shops: unrefrigerated until day 18 |
| Bread | not recommended (stales) | 3 months | 2–5 days |
| Jam, opened | 6–12 months | — | — |
| Pesto / tomato paste, opened | 5–7 days | 3–6 months in portions | — |
| Mayonnaise, opened | 2 months | — | — |
| Opened canned food | 3–4 days in a closed container (not in the can) | 2–3 months | — |
| Pasta, rice, lentils (dry) | — | — | 1–2 years |
| Flour (white / whole-grain) | — | — | 6–12 / 3–6 months |
| Canned acidic (tomatoes, fruit) / low-acid (veg, meat) | — | — | 12–18 months / 2–5 years |

Sources: USDA FoodKeeper and cold-storage chart (4), Verbraucherzentrale (2, 5), USDA shelf-stable
guidance (7). Labels: [MODERATE] — agencies differ by a day or two; the rice line follows German
consumer advice on *Bacillus cereus*, whose toxins survive reheating. [STRONG] for mechanism (8)

## Always discard

- Anything **past its use-by date** (Verbrauchsdatum). [STRONG] (1)
- **Mould on soft or moist foods:** bread, soft cheese, yogurt, cooked food, soft fruit, jam
  made at home, nuts. Mould threads and toxins spread invisibly; cutting, heating or freezing does
  not remove toxins. [STRONG] (5, 9)
- Small mould spot on **hard cheese or hard vegetables** (carrot, cabbage): cut away generously
  (≥ 1–2 cm) — the usual exception. [MODERATE] (5)
- **Bulging, leaking, spurting or badly dented cans/jars**, or broken seals. [STRONG] (7)
- Cooked food left > 2 h at room temperature (> 1 h in heat). [STRONG] (4)
- Anything that smells off, fizzes unexpectedly, or that you are unsure about after use-by-type
  storage. When in doubt, throw it out. [OPINION]

## How body-os uses this

- **Tracked:** pantry items with `date_kind` (`use_by` / `best_before` / `none`), `expires`
  (printed or estimated from the table above, `expires_est: true`), opened state, discards.
- **Agent rules:** `use_by` past → `discard`; `best_before` past → `check` with a `check_hint`
  from the category table (e.g. "look for mould, sniff for sour smell; eggs only fully cooked").
- **Weekly review question:** "What did I throw away and why — buy less, freeze earlier, or cook
  it sooner?"

## Not medical advice — see a doctor if …

- vomiting/diarrhoea with high fever, blood in stool, signs of dehydration, or lasting > 3 days;
- pregnant, elderly or immunocompromised people with fever after eating risky foods (listeria);
- **double vision, drooping eyelids, slurred speech or difficulty swallowing** after eating home
  preserves or damaged cans — possible botulism: emergency (112).

## Sources

1. Regulation (EU) 1169/2011 (Art. 24 use-by) — EUR-Lex: https://eur-lex.europa.eu/eli/reg/2011/1169/oj
2. Verbraucherzentrale — MHD is not the same as Verbrauchsdatum: https://www.verbraucherzentrale.de/wissen/lebensmittel/gesund-ernaehren/mindesthaltbarkeitsdatum-mhd-ist-nicht-gleich-verbrauchsdatum-13452
3. EFSA Safe2Eat — food date labelling (use-by is about safety, even if food looks and smells fine): https://www.efsa.europa.eu/en/safe2eat/food-date-labelling
4. USDA FoodSafety.gov — cold food storage chart / FoodKeeper app: https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts
5. Stiftung Warentest — mould on food (which foods to discard): https://www.test.de/Lebensmittel-Schimmels-schlimme-Sporen-1133015-1134853/
6. Utopia summary of BZfE egg-labelling rules (MHD ≤ 28 days, cooling from day 18): https://utopia.de/ratgeber/eier-und-ihre-haltbarkeit-das-solltest-du-wissen/
7. Utah State University Extension — storing canned goods (USDA-based): https://extension.usu.edu/preserve-the-harvest/research/storing-canned-goods.php
8. Pharmazeutische Zeitung — avoiding "fried rice syndrome" (*B. cereus*): https://www.pharmazeutische-zeitung.de/fried-rice-syndrom-vermeiden-165908/
9. aponet — why cutting and heating do not make mouldy food safe: https://www.aponet.de/artikel/schimmel-auf-lebensmitteln-warum-erhitzen-und-abschneiden-nicht-reicht-32763
