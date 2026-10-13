# Interview catalog

Each question: **ID — title**, `ask-if` (default: always), what to ask, and the default recommendation
logic. Store answers where `→` points. Adapt wording to the user; skip what is already answered.

## G — Goals and baseline

**G1 — Main goals.** Options: lose fat · build muscle · energy/sleep · endurance · longevity/prevention ·
"just understand where I stand". Ask for one primary goal. → `profile.md` Goals
*Recommend:* if unsure, a 2–4 week baseline first, then pick a goal from data.

**G2 — Baseline facts.** Height, weight (rough is fine), age range, sex (for energy formulas, optional),
known conditions, medications, allergies/intolerances, injuries. → `profile.md` Baseline
*Note:* triggers SAFETY.md checks (age < 18, pregnancy, conditions).

**G3 — Daily effort budget.** ~1 min (free text) · ~5 min (weight, meals roughly, water, sleep) ·
15+ min (weighing food, full macros). → `settings.json` `effort`
*Recommend:* ~5 min with a 1-minute fallback; precise counting only as a time-boxed experiment.

**G4 — Scope.** Which areas: nutrition · drinks (water, caffeine, alcohol) · movement/training · sleep ·
body metrics · labs/doctor · energy/mood/stress · substances/medication/supplements · symptoms ·
pantry & cooking. → `settings.json` `modules`
*Recommend:* all except irrelevant ones; energy/mood/stress is the most connecting signal.

**G5 — Learning style.** Along the way · structured knowledge pages · both. → `AGENT.md`
*Recommend:* both, always linked to the user's own numbers.

**G6 — Output.** Chat only · files + charts on request · dashboard. → `ROADMAP` of `me/`
*Recommend:* files + Datasette immediately, custom dashboard once the metric list is stable.

## P — Privacy and setup

**P1 — Storage.** Local `me/` with its own git and no remote (recommended) vs private remote for multi-device.
Explain: model provider sees what the agent reads. → `settings.json` `privacy`

**P2 — What the agent may read.** Everything · summaries preferred, photos analysed not stored,
no identifiers (recommended) · exclude topics. → `AGENT.md` Privacy

**P3 — Check-in channel.** Desktop session · phone via remote session to the computer · phone notes
pasted later. → `settings.json` `checkin`
*Recommend:* phone + desktop if the agent tool supports a local remote session; otherwise notes.

## D — Devices

**D1 — What do you own?** Phone OS (iPhone/Android), bathroom scale, kitchen scale, tape measure,
BP monitor, wearable. → `settings.json` `devices`

**D2 — Buy anything?** ask-if: no BP monitor or no wearable and goals involve sleep/endurance/longevity.
Present criteria, not products: validated upper-arm BP monitor; wearable matching the phone
(Apple Health / Health Connect), sleep comfort, charging routine, subscription, export. Ask budget.
→ `plans/devices-buying-criteria.md`

**D3 — Automatic data flow.** ask-if: wearable owned or planned. Options: phone shortcut posting to a
local receiver (free, best-effort) · paid exporter app to the same receiver · manual export every 1–2
weeks. → `settings.json` `devices.sync`
*Recommend:* free shortcut first, paid app as fallback, after the wearable arrives.

## M — Measurement list

**M1 — Confirm metric list.** Propose daily (morning weight, bed/wake, sleep quality, wakeups; meals,
water, caffeine+time, alcohol, substances; evening energy/mood/stress), training logs, weekly (waist,
BP), monthly (circumferences, field test, optional photos), yearly (labs). Remove what the user
rejects. → `settings.json` `metrics`

## S — Safety screens

**S1 — Eating.** Gently: "Has food, weight or calorie counting ever caused you stress or been a
problem?" ask-if: nutrition active. If yes/unsure → SAFETY.md §2. → `AGENT.md`

**S2 — Last check-up and labs.** When, findings, copy available? → `doctor/checklist.md`
*Recommend:* get a copy (in DE: right to a copy; also ePA), recheck anything flagged.

## C — Substances

**C1 — What and how much.** Tobacco (form), cannabis, alcohol, caffeine, other. Years of use.
ask-if: G4 includes substances. → `profile.md`

**C2 — Approach.** Count only · baseline then decide · harm reduction · reduce/quit as goal · don't
discuss. → `plans/substances.md`
*Recommend:* baseline 2–4 weeks with time + trigger per use, then decide. Mixed tobacco-cannabis:
point out nicotine as the main dependence driver; separating them is a strong first lever.

**C3 — History.** ask-if: C2 is reduce/quit. Past attempts, methods, how long, what brought them back
(triggers). → `plans/substances.md`

**C4 — Aids and plan B.** ask-if: C2 is reduce/quit. Aids now (NRT, medication via doctor, courses,
vaporizer) or unaided first. If unaided: agree a pre-defined plan-B rule (e.g. back to old level
within 2 weeks → next attempt with support). → `AGENT.md` + plan

## T — Training

**T1 — Facilities and preferences.** Gym access, home equipment, outdoor sports liked, days/week,
history, injuries. → `profile.md`

**T2 — Structure.** e.g. 3× full-body strength + 1× easy endurance (muscle goal) · 2+2 · split.
→ `plans/training.md`
*Recommend:* match primary goal; first 2 weeks light; fixed plan A/B so logging is "A done".

## N — Nutrition

**N1 — Logging method.** Photos/text estimated by agent against local nutrient DB · tracking app ·
calibration phase with kitchen scale. → `settings.json` `nutrition`
*Recommend:* photos/text; weight trend is the ground truth; optional 2-week calibration.

**N2 — Diet and preferences.** Eats everything / vegetarian / vegan / other; dislikes; intolerances;
favourite cuisines; weekday cooking time; cooking skill. → `profile.md` Food

**N3 — Nutrient source.** By country: DE → BLS 4.0; US → USDA FDC; everywhere → Open Food Facts for
packaged goods. → `settings.json` `nutrition.sources`

## K — Pantry and cooking (module `pantry`)

**K1 — Household.** Alone or shared? People eating from the same fridge; default portions; others'
dislikes/intolerances only with their consent; never track others. → `settings.json` `household`

**K2 — Kitchen devices.** Stove, oven, microwave, air fryer, Thermomix/multicooker, pressure cooker …
Recipe platforms owned (e.g. Cookidoo) — reference by name/link only, never copy. → `settings.json` `kitchen`

**K3 — Purchase input.** Receipt photo (best) · photo of groceries · text. One summary confirmation per
purchase, never item-by-item questions. Store prices? → `settings.json` `pantry`

**K4 — Pantry upkeep.** Automatic (purchases add, logged meals subtract, weekly fridge photo
reconciles) · light (items leave on expiry or "used up"). → `settings.json` `pantry.mode`

**K5 — Suggestions.** When (on request + proactive for expiring items), how many (default 4: ≥1 very
simple, 1–2 medium, 1 more ambitious with a learning note), cuisines to rotate, scoring rubrics.
→ `settings.json` `cooking`

**K6 — Shopping list.** On request · plus at weekly review · fixed meal plan. → `settings.json`
*Recommend:* on request + weekly review, no rigid plan.

## R — Rhythm and style

**R1 — Reviews.** Weekly day/time, monthly day, reminders (user's phone vs scheduled agent task).
→ `settings.json` `reviews`

**R2 — Coach style.** Direct and honest · reserved (answer only) · gentle. → `AGENT.md`

**R3 — Change sequence and start.** Baseline length, what changes when, start date.
→ `plans/start-plan.md`
