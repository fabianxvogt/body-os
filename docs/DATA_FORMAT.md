# Data format

All personal data lives in `me/` (see [ARCHITECTURE.md](ARCHITECTURE.md)); in household mode in each
member's instance folder, with the kitchen files in `household/` ([below](#household-mode-household)). Plain text is the source of
truth; `data/body-os.sqlite` is a disposable build product (`python3 tools/bos.py build`).

## Files in `me/`

| Path | Content | Format |
|---|---|---|
| `me/settings.json` | locale, timezone, active modules, household, devices, review schedule, phases, goals, costs ([below](#settingsjson)) | JSON |
| `me/profile.md` | baseline facts and goals from the interview (no name, birth date, address, insurance number) | Markdown |
| `me/AGENT.md` | personal agent rules (coach style, plan rules, priorities) | Markdown |
| `me/log/YYYY/YYYY-MM.jsonl` | health events, one JSON object per line, append-only by convention | JSONL |
| `me/pantry/pantry.jsonl` | pantry events (purchases, consumption, discards, adjustments); `household/` in household mode | JSONL |
| `me/recipes/cookbook.jsonl` | suggested/cooked recipes and ratings; `household/` in household mode | JSONL |
| `me/plans/*.md` | current plans (training, start plan, substance plan …) | Markdown |
| `me/plans/training.json` | current working weights, agent-maintained: `{exercises: [{name, plan, sets, reps, kg, next_kg?}]}` | JSON |
| `me/pantry/shopping-list.md` | shopping list the agent writes at the weekly review (checkboxes `- [ ]` allowed); `household/` in household mode | Markdown |
| `me/reviews/YYYY-Www.md`, `me/reviews/YYYY-MM.md` | weekly and monthly reviews; the dashboard shows the first item under a heading containing "Fokus"/"Focus" as the week's focus | Markdown |
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
| `price_eur` | no | money paid for this event (meal eaten out, drink bought on the go, substance bought by the unit); see [costs](#costs) |

## Event types

| `type` | Fields |
|---|---|
| `weight` | `kg` |
| `sleep` | `bed` (ts), `wake` (ts), `quality` 1–5, `wakeups` int, `dur_min` (device, optional), `deep_min`/`rem_min` (device, optional) |
| `meal` | `slot` (`breakfast`/`lunch`/`dinner`/`snack`), `desc`, `items` [{`name`, `g`, `food_id`?, `kcal`?, `protein_g`?}], `kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `pantry_used` [{`item_id`, `qty`}] — item-level `protein_g` feeds "top protein sources" |
| `drink` | `kind` (`water`/`coffee`/`tea`/`alcohol`/`soft`/`other`), `ml`, `caffeine_mg`?, `alcohol_units`? (1 unit = 10 g ethanol) |
| `substance` | `kind` (`joint`/`cigarette`/`vape`/`cannabis_vape`/`nicotine_replacement`/`other`), `count` (default 1), `tobacco` bool, `trigger` (free text: `stress`, `boredom`, `after-meal`, `break`, `evening`, `social` …), `g`? (cigarette: tobacco g; joint/vape: cannabis g) |
| `training` | `kind` (`strength`/`run`/`bike`/`walk`/`sport`/`other`), `plan` (e.g. `A`), `dur_min`, `sets` [{`ex`, `kg`, `reps` [int]}], `distance_km`?, `avg_hr`?, `rpe` 1–10? |
| `checkin` | `energy` 1–5, `mood` 1–5, `stress` 1–5 (any subset) |
| `symptom` | `desc`, `severity` 1–5 |
| `measure` | `metric` (`waist_cm`, `arm_cm`, `chest_cm`, `thigh_cm`, `resting_hr`, `hrv_ms`, `steps`, `vo2max`, `bp`, `test_<name>` for field tests …), `value`, `unit`; for `bp`: `sys`, `dia`, `pulse` |
| `lab` | `test`, `value`, `unit`, `ref_low`?, `ref_high`?, `lab_date` |
| `note` | `text`, `tags` [] |

Unknown extra fields are allowed and preserved. Units are metric. Ratings are 1 (worst) – 5 (best);
for `stress`, 5 = most stressed.

## Pantry events (`pantry/pantry.jsonl`)

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
| `gone` | fully consumed, discarded, or adjusted to gone (`gone_at` = date; discarded items count as food waste: `price_eur` × share left) |

Items in `check` or `discard` are never used in cooking suggestions.

## Cookbook (`recipes/cookbook.jsonl`)

`id`, `ts`, `name`, `cuisine`, `device` (`stove`/`oven`/`thermomix`/`microwave`/`none`),
`minutes`, `servings`, `simplicity` 1–5, `nutrition_score` 1–5, `per_serving` {`kcal`, `protein_g`},
`status` (`suggested`/`cooked`), `rating` (`up`/`down`/null), `skill`? (technique learned), `source`
(`generated`, `cookidoo:<name>`, URL), `notes`.

## Household mode (`household/`)

Private git repo next to the instance folders (git-ignored, no remote). Example:
[examples/demo-household/](../examples/demo-household/).

`household/household.json`:

```json
{"schema": 1, "name": "Home",
 "members": [{"id": "alex", "name": "Alex", "color": "blue", "path": "me", "consent": true},
             {"id": "sam", "name": "Sam", "color": "orange", "path": "people/sam", "consent": false}],
 "default_member": "alex"}
```

| Field | Rule |
|---|---|
| `id` | `[a-z0-9][a-z0-9_-]{0,31}`, unique; used by `--profile` and `?profile=` |
| `name` | display name in the dashboard (a first name or nickname is enough) |
| `color` | avatar colour slot: `blue`, `orange`, `aqua`, `yellow`, `magenta`, `green`, `violet`, `red` |
| `path` | instance folder relative to the folder containing `household/` (the engine root), e.g. `me`, `people/sam`; no `..`, no hidden or engine folders, no folder inside another member's |
| `consent` | `true` once the member did their own interview and agreed to tracking; `false` = nothing is logged for them |
| `default_member` | profile used when `--profile` is not given (optional; else the member at `me/`) |

`household/settings.json`: shared keys that override each member's settings — `language`,
`timezone` (only if the member has none), `household` (`members`, `portions_default`, `shared_notes`),
`kitchen`, `pantry`, `cooking`, and `costs` (merged key by key; typically only `currency`).

`household/pantry/pantry.jsonl`, `household/pantry/shopping-list.md`, `household/recipes/cookbook.jsonl`:
same formats as above, one kitchen for all members.

### server.json (LAN access)

`household/server.json` (single-user mode: `data/server.json`), mode 0600, both git-ignored:
`{"schema": 1, "key": "<43-char urlsafe token>", "created": "<ISO timestamp>", "allowed_hosts": []}`.
`key` is the household key (32 random bytes); `bos dashboard --rotate-key` replaces it.
`allowed_hosts` lists extra Host names the dashboard accepts (e.g. a router DNS name).

## Food reference data (`data/`, git-ignored)

`bos foods-import` builds `data/foods.sqlite` from public sources: BLS 4.0 (Germany, CC BY 4.0,
attribution: Max Rubner-Institut (2025), *Bundeslebensmittelschlüssel (BLS), Version 4.0*,
doi:10.25826/Data20251217-134202-0) and, optionally, Open Food Facts (ODbL). Values are per 100 g
edible portion; missing values stay missing, never zero.

## settings.json

Written during onboarding, edited by the agent when plans change. Everything below is **optional**;
the dashboard shows an empty state or a hint when a key is missing. Defaults: [templates/me/settings.json](../templates/me/settings.json).

| Key | Shape | Used for |
|---|---|---|
| `language`, `timezone`, `modules`, `reviews`, … | see template | basics (German dashboard when `language` is `de`) |
| `phases` | `[{id, name, from, to?, focus, targets?: {tobacco_per_day?}}]` | plan phases; current phase banner ("day X of Y"), baseline = phase `baseline` (else the first phase), phase target line |
| `decisions` | `[{date, title, status: open\|done, note?}]` | next open decision with days left; decision list in the journal |
| `goals.weight_rate_kg_month` | `[lo, hi]` kg per month, e.g. `[-2, -0.5]` | weight goal corridor, anchored at the first weight of the current (else first) phase |
| `goals.protein_g_per_kg` | `[lo, hi]`, e.g. `[1.6, 2.0]` | protein target band = goal × latest 7-day weight (else `nutrition.targets.protein_g`) |
| `nutrition.targets` | `{protein_g?, kcal?}` number or `[lo, hi]` | target lines/bands |
| `training.sessions_per_week` | int (default 4) | weekly plan line |
| `training.schedule` | `{"mon": "strength", "sat\|sun": "endurance"}` | "due today" (`sat\|sun` = either day); value matches a training `kind`, a category (`strength`, `endurance` = run/bike, `other`) or a `plan` letter |
| `measurements` | `{waist_cm: "weekly:mon", circumferences: "monthly:first-sun", bp: "2x-week"}` | due measurements: `weekly:<day>` due on that weekday unless logged in the last 6 days; `monthly:first-<day>` due on that day unless logged this month; `<n>x-week` = n per ISO week. `circumferences` covers waist/arm/chest/thigh/hip/neck |
| `checklist` | default `["weight", "sleep", "meals>=2", "checkin"]` | today's check-in list; any event type works, `name>=n` sets a minimum count |
| `substances.plan_b` | `{window_days: 14, phase_id: "tobacco-step-1", threshold_pct_of_baseline: 90}` | plan-B check once that phase has started: last ≤ 7 full days vs. baseline; "Plan B due" when ≥ threshold after the window |
| `reviews.weekly` | e.g. `"sunday-evening"` (first three letters = weekday) | "weekly review due" on that day when `reviews/YYYY-Www.md` is missing |
| `costs` | see below | spending estimates |
| `compare.share` | list of groups, default `["consistency", "training", "sleep", "hydration", "protein"]`; opt-in: `"wellbeing"`, `"substances"`; `[]` = not in the comparison | household Compare tab ([below](#compare-household-comparison)) |
| `display_name`, `color` | single-user mode only: avatar name and colour slot in the dashboard (default "Me"/"Ich", `blue`) | dashboard header |

### Compare (household comparison)

Household mode only (`GET /api/compare?days=N`, dashboard tab Compare / Vergleich). It compares
habits and progress **relative to each member's own plan**, never body numbers: weight, kcal, body
measures, blood pressure and labs are not part of it (the protein target uses the weight internally;
only the percentage leaves). Members with `consent: false` or an empty `compare.share` are never
included. A group is shown for the members who share it and ranked only when ≥ 2 share it;
`substances` appears only when **every** compared member shares it. `protein` is never shared while
`nutrition.show_numbers` is `false` ([SAFETY.md](../SAFETY.md) §2).

| Group | Metrics (n behind each value) |
|---|---|
| `consistency` | % of days with a complete check-in (`checklist`), current and longest streak |
| `training` | sessions vs. own `training.sessions_per_week` (pro rata; this week: progress towards the plan), active minutes per week, strength progress (e1RM change of each lift with ≥ 2 sessions in the period, mean) |
| `sleep` | mean hours, % nights ≥ 7 h, bedtime spread (SD, lower is better), mean quality |
| `hydration` | mean water L/day on days with water logged |
| `protein` | mean % of own protein target midpoint (`goals.protein_g_per_kg` × latest 7-day weight, else `nutrition.targets.protein_g`) |
| `wellbeing` (opt-in) | mean energy, mood, stress (lower is better) |
| `substances` (opt-in, all) | tobacco-free logged days, % change of tobacco uses vs. own baseline phase (lower is better) |

Only days since a member's first log count. Ties (equal as displayed) have no leader. Plan-relative
values rank up to 100 % (sleep up to 8 h): when everyone has met their plan nobody "leads"; values
above 150 % are reported as `capped`.

### Costs

`costs: {currency: "EUR", tobacco_eur_per_g, tobacco_g_per_use, cannabis_eur_per_g, cannabis_g_per_use,
alcohol_eur_per_unit, coffee_eur_per_cup_home}` (all `null` = unknown). Categories, in this fixed order:

| Category | Source |
|---|---|
| groceries | pantry purchase items with `price_eur` |
| eating & drinking out | `meal`/`drink` events with `price_eur` (home-cooked meals add nothing: groceries are counted at purchase) |
| tobacco | `price_eur`, else ≈ `tobacco_g_per_use` (or a cigarette's `g`) × `tobacco_eur_per_g` × `count`; joints with `tobacco: true` add one tobacco portion |
| cannabis | `price_eur`, else ≈ (event `g` or `cannabis_g_per_use`) × `cannabis_eur_per_g` (joints, `cannabis_vape`) |
| alcohol | `price_eur`, else ≈ `alcohol_units` × `alcohol_eur_per_unit` |
| coffee | `price_eur` (bought), else ≈ `coffee_eur_per_cup_home` per coffee |

Derived costs are estimates and marked "≈" in the dashboard. Events whose cost cannot be computed are
counted as "without a price" and the missing setting is named.

