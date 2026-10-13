# Onboarding interview — how to run it

Goal: reach a shared understanding of the person, then generate their private `me/` folder.
Questions live in [CATALOG.md](CATALOG.md). Safety rules in [../SAFETY.md](../SAFETY.md) apply throughout.

## Process

1. **Open.** Explain in two sentences what body-os does, that you are not a doctor, and that
   everything you read goes to the model provider (data itself stays on this computer). Ask which
   language to use; continue in it.
2. **Work in rounds.** The *frontier* = every catalog question whose `ask-if` condition is met and
   whose prerequisites are answered. Ask the whole frontier in one round, numbered, each with your
   **recommended answer** (➡️) and why. Wait for answers. Recompute the frontier. Repeat.
   - Format per question: `❓ **Q<n> — <title>**: <question, options a/b/c>` then `➡️ <recommendation>`.
   - Typical rounds: 1) goals/effort/scope/devices/output/learning, 2) privacy, substances,
     training, nutrition method, metric list, purchases, doctor, check-in channel,
     3) module details, review rhythm, coach style, start plan.
   - Ask facts only the user knows. Look up everything else yourself (files, web, tools).
   - Accept voice-style rambling answers; extract decisions; restate what is settled at the top
     of each round in a short bullet list.
   - New topics the user raises become new branches; add questions for them.
3. **Safety checks** (fold naturally into early rounds): age ≥ 18, pregnancy, known conditions,
   medications, eating-disorder screen (`S1`), red flags. Apply SAFETY.md immediately if triggered.
4. **Summary.** When the frontier is empty, present one compact summary (goals, privacy, what is
   tracked and how, modules, plan phases, reviews, coach style, what you will set up now vs later)
   and ask for an explicit go.
5. **Generate `me/`** after the go:
   - `python3 tools/bos.py init` (copies `templates/me/`, creates the private git repo, enables hooks).
   - Fill `me/settings.json`, `me/profile.md`, `me/AGENT.md` from the answers (no name, birth date,
     address, insurance numbers — store age range or year only if needed).
   - Write starting plans in `me/plans/` for active modules (start plan for the first 2 weeks,
     training plan, substance plan, doctor checklist, device buying criteria — as applicable).
   - `python3 tools/bos.py foods-import` if nutrition is active and the data source is available.
   - `python3 tools/bos.py doctor`, then commit inside `me/`.
6. **First check-in instructions.** Tell the user exactly what to send tomorrow morning and how to
   reach the session from their phone if they use one.

## Onboarding another household member

Each adult in the household gets **their own interview and their own consent**; nobody is tracked
because someone else set them up.

1. Household mode must exist: `python3 tools/bos.py household init --member-id <id> --member-name <Name>`
   (registers the existing `me/` and moves pantry, cookbook and shopping list to `household/`).
2. `python3 tools/bos.py profile add <id> --name <Name> [--color <slot>]` creates `people/<id>/` (its own
   private git repo, `consent: false`, no modules). The dashboard shows them a calm "not set up yet" card.
3. Run this interview **with that person** (they answer, not the first member). Same rules: no real
   name beyond the display name, explain what is stored and that the agent's reads go to the model
   provider, safety checks, explicit go.
4. Only after their go: `python3 tools/bos.py profile consent <id>`, fill `people/<id>/settings.json`,
   `profile.md`, `AGENT.md` and plans, and commit inside `people/<id>/`. Kitchen preferences that
   concern everybody go to `household/settings.json` (`household.shared_notes`) with their consent.
5. Tell them how to open the dashboard (same device link; they pick their avatar) and that every
   household member with the link can see their charts.

Withdrawn consent: `profile consent <id> --revoke` stops logging; ask whether to delete their folder.

## Re-interview

Triggered by "my goals changed", a new device, a new household situation, or at a monthly review
when a phase ends. Ask only the affected modules' questions, show a diff of what changes in `me/`,
apply after a go.

## Principles learned from the first real interview

- Start with a baseline period (2–4 weeks) before changing behaviour; data first, then decisions.
- Effort budget decides everything; offer a 1-minute fallback for lazy days.
- Change one big thing at a time; sequence changes (e.g. training → substance step → nutrition).
- For habits the user has failed to change before, design for minimal willpower (environment,
  substitution, pre-agreed plan B) and record the plan-B rule explicitly.
- Never ask about every item individually (e.g. each grocery product); batch into one summary
  confirmation.
