# Data format

All personal data lives in `me/` (see [ARCHITECTURE.md](ARCHITECTURE.md)). Plain text is the source of
truth; `data/body-os.sqlite` is a disposable build product (`python3 tools/bos.py build`).

## Files in `me/`

| Path | Content | Format |
|---|---|---|
| `me/settings.json` | locale, timezone, active modules, household, devices, review schedule | JSON |
| `me/profile.md` | baseline facts and goals from the interview (no name, birth date, address, insurance number) | Markdown |
| `me/AGENT.md` | personal agent rules (coach style, plan rules, priorities) | Markdown |
| `me/log/YYYY/YYYY-MM.jsonl` | health events, one JSON object per line, append-only by convention | JSONL |
| `me/pantry/pantry.jsonl` | pantry events (purchases, consumption, discards, adjustments) | JSONL |
| `me/recipes/cookbook.jsonl` | suggested/cooked recipes and ratings | JSONL |
| `me/plans/*.md` | current plans (training, start plan, substance plan …) | Markdown |
| `me/reviews/YYYY-Www.md`, `me/reviews/YYYY-MM.md` | weekly and monthly reviews | Markdown |
| `me/doctor/` | doctor checklists, transcribed lab values (raw PDFs optional, never required) | Markdown |
| `me/inbox/` | device exports waiting for import (JSON/CSV) | any |

`me/` is its own private git repository. Corrections are made by editing the line; git history is the audit trail.

## Common event fields (`me/log`)

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | unique string; `bos log` generates `<type>-<YYYYMMDDHHMMSS>-<4 hex>` |
| `ts` | yes | ISO 8601 local time with offset, e.g. `2026-10-14T07:30:00+02:00` (time the thing happened, not logging time) |
| `type` | yes | one of the types below |
| `src` | no | `chat` (default), `photo`, `device`, `import`, `estimate` |
| `conf` | no | `high`, `med`, `low` — confidence of estimated values |
| `note` | no | free text |

## Event types

| `type` | Fields |
|---|---|
| `weight` | `kg` |
| `sleep` | `bed` (ts), `wake` (ts), `quality` 1–5, `wakeups` int, `dur_min` (device, optional), `deep_min`/`rem_min` (device, optional) |
| `meal` | `slot` (`breakfast`/`lunch`/`dinner`/`snack`), `desc`, `items` [{`name`, `g`, `food_id`?}], `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `pantry_used` [{`item_id`, `qty`}] |
| `drink` | `kind` (`water`/`coffee`/`tea`/`alcohol`/`soft`/`other`), `ml`, `caffeine_mg`?, `alcohol_units`? (1 unit = 10 g ethanol) |
| `substance` | `kind` (`joint`/`cigarette`/`vape`/`cannabis_vape`/`nicotine_replacement`/`other`), `count` (default 1), `tobacco` bool, `trigger` (free text: `stress`, `boredom`, `after-meal`, `break`, `evening`, `social` …), `g`? |
| `training` | `kind` (`strength`/`run`/`bike`/`walk`/`sport`/`other`), `plan` (e.g. `A`), `dur_min`, `sets` [{`ex`, `kg`, `reps` [int]}], `distance_km`?, `avg_hr`?, `rpe` 1–10? |
| `checkin` | `energy` 1–5, `mood` 1–5, `stress` 1–5 (any subset) |
| `symptom` | `desc`, `severity` 1–5 |
| `measure` | `metric` (`waist_cm`, `arm_cm`, `chest_cm`, `thigh_cm`, `resting_hr`, `hrv_ms`, `steps`, `vo2max`, `bp`, `test_<name>` …), `value`, `unit`; for `bp`: `sys`, `dia`, `pulse` |
| `lab` | `test`, `value`, `unit`, `ref_low`?, `ref_high`?, `lab_date` |
| `note` | `text`, `tags` [] |

Unknown extra fields are allowed and preserved. Units are metric. Ratings are 1 (worst) – 5 (best);
for `stress`, 5 = most stressed.

## Pantry events (`me/pantry/pantry.jsonl`)

| `type` | Fields |
|---|---|
| `purchase` | `store`?, `items` [pantry item] |
| `consume` | `item_id`, `qty` (same unit as item; omit = all), `meal_id`? |
| `discard` | `item_id`, `reason` (`expired`, `spoiled`, `other`) |
| `adjust` | `item_id`, `qty`? , `status`? (`present`/`gone`), `opened`? — from a fridge photo or a user remark |
| `open` | `item_id`, `expires`? (new estimated expiry once opened) |

Pantry item: `item_id` (unique), `name`, `qty`, `unit` (`g`, `ml`, `pcs`), `price_eur`?, `food_id`?,
`category`, `storage` (`fridge`/`freezer`/`pantry`), `date_kind` (`best_before` = MHD,
`use_by` = Verbrauchsdatum, `none` = fresh produce without date), `expires` (date),
`expires_est` (bool, true when estimated), `check_hint`? (what to inspect once past the date).

Derived status (`bos pantry`):

| Status | Rule |
|---|---|
| `ok` | more than 2 days before `expires` |
| `soon` | `expires` within 2 days |
| `check` | past `expires` for `best_before` or `none` — inspect before use (look, smell, texture), use `check_hint` |
| `discard` | past `expires` for `use_by`, or `check` for more than the item's grace (default 7 days `best_before`, 2 days `none`) |
| `gone` | fully consumed, discarded, or adjusted to gone |

Items in `check` or `discard` are never used in cooking suggestions.

## Cookbook (`me/recipes/cookbook.jsonl`)

`id`, `ts`, `name`, `cuisine`, `device` (`stove`/`oven`/`thermomix`/`microwave`/`none`),
`minutes`, `servings`, `simplicity` 1–5, `nutrition_score` 1–5, `per_serving` {`kcal`, `protein_g`},
`status` (`suggested`/`cooked`), `rating` (`up`/`down`/null), `skill`? (technique learned), `source`
(`generated`, `cookidoo:<name>`, URL), `notes`.

## Food reference data (`data/`, git-ignored)

`bos foods-import` builds `data/foods.sqlite` from public sources: BLS 4.0 (Germany, CC BY 4.0,
attribution: Max Rubner-Institut (2025), *Bundeslebensmittelschlüssel (BLS), Version 4.0*,
doi:10.25826/Data20251217-134202-0) and, optionally, Open Food Facts (ODbL). Values are per 100 g
edible portion; missing values stay missing, never zero.
