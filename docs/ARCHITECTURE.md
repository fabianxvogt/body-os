# Architecture

body-os is a **public engine** plus one **private instance folder** per user.

```
body-os/                 public git repo (engine) — clone it
├── AGENTS.md            agent manual: onboarding, check-ins, reviews, privacy rules
├── interview/           onboarding question catalog (modular, branching)
├── modules/             what each module tracks, how check-ins and reviews handle it
├── knowledge/           evidence-labelled learning pages
├── tools/bos.py         CLI: log, validate, summaries, pantry status, SQLite build, food lookup, dashboard
├── templates/me/        skeleton copied into me/ during onboarding
├── examples/demo-me/    synthetic persona for tests and demos (fictional)
└── me/                  ← PRIVATE: git-ignored here, its own local git repo, never pushed
```

## The one rule

| Change | Goes to |
|---|---|
| Generic: features, modules, interview questions, knowledge, tools, docs | engine repo → commit → push |
| Personal: data, profile, plans, personal agent rules, reviews | `me/` → commit in the `me/` repo only |

Personal tailoring never edits engine files. The engine reads `me/settings.json` and `me/AGENT.md`
to adapt. If a personal need reveals a missing generic feature, build the generic feature in the
engine and configure it in `me/`.

## Guards

- `.gitignore` excludes `/me/` and `/data/`.
- `.githooks/pre-commit` and `pre-push` refuse commits/pushes that contain `me/`, `data/`, `.env*` or
  files matching personal-data patterns. Enable once per clone: `git config core.hooksPath .githooks`
  (`bos init` does this).
- `me/` should have **no remote**. `bos doctor` warns if it has one.

## Data flow

```
chat / photo / device export ──agent──▶ me/*.jsonl ──bos build──▶ data/body-os.sqlite ──▶ Datasette dashboard
public food data ──bos foods-import──▶ data/foods.sqlite ──bos food──▶ nutrient estimates
```

Agents read summaries (`bos summary`) before raw logs to minimise what leaves the machine.
