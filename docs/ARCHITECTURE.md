# Architecture

body-os is a **public engine** plus **private folders**: one instance folder per person and, in
household mode, one shared household folder for the kitchen.

```
body-os/                 public git repo (engine) — clone it
├── AGENTS.md            agent manual: onboarding, check-ins, reviews, privacy rules
├── interview/           onboarding question catalog (modular, branching)
├── modules/             what each module tracks, how check-ins and reviews handle it
├── knowledge/           evidence-labelled learning pages
├── tools/bos.py         CLI: log, validate, summaries, pantry, SQLite build, food lookup, dashboard, household
├── tools/dashboard/     dashboard web UI (static files, vendored ECharts + QR code, PWA manifest/icons)
├── templates/me/        skeleton copied into a new instance folder
├── examples/            synthetic data: demo-me/ (single user), demo-household/ (two members)
├── me/                  ← PRIVATE: first person's instance, its own git repo, git-ignored, never pushed
├── people/<id>/         ← PRIVATE: further household members, one git repo each (household mode)
└── household/           ← PRIVATE: household.json, shared kitchen, server.json (household mode)
```

## Single user (default)

`me/` alone works; nothing else is needed. Pantry, cookbook and shopping list live in `me/`.

## Household mode

Created with `bos household init` (registers `me/` as the first member and moves its kitchen files
into `household/`), extended with `bos profile add <id>`.

```
household/                         private git repo, no remote
├── household.json                 members [{id, name, color, path, consent}], default_member
├── settings.json                  shared: language, household portions, kitchen, pantry, cooking, costs.currency
├── pantry/pantry.jsonl            ┐
├── pantry/shopping-list.md        ├ one kitchen for everybody
├── recipes/cookbook.jsonl         ┘
└── server.json                    household key for LAN access (mode 0600)
me/            → member "alex"     personal: log, plans, reviews, profile, settings (own repo)
people/sam/    → member "sam"      personal, consent: false until Sam's own interview (own repo)
```

- **Which instance?** `--profile <id>` (default: `default_member`, else `me/`). Member paths are
  relative to the folder containing `household/` (the engine root). `--household DIR` points
  elsewhere (tests, demos); an explicit `--me DIR` without `--household` stays single-user unless DIR
  is a registered member's folder (then that member's consent applies). Household mode without a
  selected member writes nothing personal.
- **Kitchen files** are read and written in `household/`. If `household/` lacks one, the member's
  own copy is used; `bos doctor` warns when both exist.
- **Settings** = the member's `settings.json` with the household's shared keys on top (language,
  `household`, `kitchen`, `pantry`, `cooking`, `costs` merged).
- **Consent.** A member with `consent: false` gets no events: `bos log` / `pantry-log` refuse, and the
  dashboard shows an onboarding hint instead of personal charts; none of their personal settings are
  served. Kitchen views still work.

## The one rule

| Change | Goes to |
|---|---|
| Generic: features, modules, interview questions, knowledge, tools, docs | engine repo → commit → push |
| Personal: data, profile, plans, personal agent rules, reviews | the person's instance folder → commit in that repo only |
| Shared kitchen: pantry, cookbook, shopping list, household settings | `household/` → commit in that repo only |

All three private kinds stay local and never get a remote. Personal tailoring never edits engine
files. If a personal need reveals a missing generic feature, build it in the engine and configure it
in the private folder.

## Guards

- `.gitignore` excludes `/me/`, `/people/`, `/household/` and `/data/`.
- `.githooks/pre-commit` and `pre-push` refuse commits/pushes that contain `me/`, `people/`,
  `household/`, `data/`, `.env*` or log-like `*.jsonl` outside `examples/` (case-insensitive).
  Enable once per clone: `git config core.hooksPath .githooks` (`bos init` does this).
- `bos doctor` checks that every instance folder and `household/` is its own git repo, has no remote
  and is ignored by the engine repo.

## Dashboard server

`bos dashboard` binds 127.0.0.1 (unchanged). `--lan` binds 0.0.0.0 for phones in the home network:

- Loopback clients need no key. Every other client needs the **household key** (`server.json`, created
  on the first `--lan` start, `--rotate-key` replaces it): cookie `bos_key`, set once by opening the
  device link `/?key=…` (HttpOnly, SameSite=Strict, 400 days; the key is stripped by a redirect).
  Without it: 401 and no data, for every path including static files.
- `/devices` (QR code + device link) answers only loopback clients.
- Host header must be a name of this machine (localhost, LAN IPv4, `<LocalHostName>.local`,
  `server.json` `allowed_hosts`): DNS-rebinding guard. Strict CSP, no CORS, read-only, GET only.
- Anyone with the key sees **all** profiles. Plain HTTP inside the home network: use it only on a
  network you trust.
- `bos service install [--lan]` (macOS) runs it as a launchd agent (`io.body-os.dashboard`); its log
  (`data/dashboard.log`, mode 0600) never contains the key — pair phones via `/devices`.

## Data flow

```
chat / photo / device export ──agent──▶ instance/*.jsonl, household/*.jsonl ──bos build──▶ data/body-os.sqlite ──▶ Datasette
instance + household files ──bos dashboard──▶ 127.0.0.1 (or LAN with key) tab dashboard, live, read-only, per profile
public food data ──bos foods-import──▶ data/foods.sqlite ──bos food──▶ nutrient estimates
```

Agents read summaries (`bos summary`) before raw logs to minimise what leaves the machine.
