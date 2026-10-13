# body-os

**An agent-operated personal health tracker you run locally.** Clone it, open it with a coding agent
(Claude Code, Codex, Gemini CLI, Cursor …), and the agent interviews you, sets up a private tracking
folder tailored to you, then becomes your daily check-in partner: it logs meals from photos, sleep,
training, substances, body metrics and your pantry, runs weekly reviews, and teaches you what the
numbers mean.

> **Status: early (v0).** Core logging, summaries, pantry expiry logic, food lookup (German BLS 4.0),
> a local multi-tab dashboard (`bos dashboard`) and a Datasette raw-table view work. Phone/wearable sync
> is on the [roadmap](ROADMAP.md). Not a medical device — see [SAFETY.md](SAFETY.md).

## How it works

```
git clone https://github.com/fabianxvogt/body-os && cd body-os
claude            # or: codex, gemini, cursor …  → "Set me up"
```

1. **Interview.** The agent asks focused questions in rounds — goals, effort budget, devices,
   privacy, training, food, substances, household, kitchen — always with a recommended answer.
   ([interview/](interview/README.md))
2. **Setup.** It creates `me/`: your private folder with its own local git repo, never pushed.
   Profile, plans, metric list and personal agent rules live there.
3. **Check-ins.** Send short messages or photos: "70.4, slept badly", a meal photo, a receipt photo,
   "A erledigt". The agent stores structured events and replies in one or two lines.
4. **Reviews.** Weekly and monthly reviews connect your data to evidence-labelled
   [knowledge](knowledge/README.md) and suggest one change at a time.

## Privacy model

- Engine (this repo) is public; **your data is not**. `me/` and `data/` are git-ignored, and git
  hooks block commits/pushes containing them ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
- Data stays on your machine as plain text (JSONL/Markdown). Whatever the agent *reads* is processed
  by your model provider — agents prefer aggregated summaries and don't store photos.

## Modules

core · sleep · nutrition · pantry & cooking · training · substances · health checks · devices ·
reviews — see [modules/](modules/README.md).

## Tools

`tools/bos.py` (Python 3.9+, stdlib only): `init`, `doctor`, `log`, `pantry-log`, `validate`,
`summary`, `pantry`, `build`, `dash` (Datasette raw tables), `dashboard` (eight tabs — Today, Body,
Nutrition, Kitchen, Sleep & energy, Substances, Training, Journal — with plan phases, due items,
goal corridors, costs and reviews; served read-only on 127.0.0.1, live from `me/`, no external
requests), `foods-import`, `food search|calc`. Tests:
`python3 -m unittest discover -s tests`.

## Data sources and credits

- Bundeslebensmittelschlüssel (BLS) 4.0, Max Rubner-Institut (2025), CC BY 4.0,
  doi:10.25826/Data20251217-134202-0 — downloaded locally, not redistributed.
- BLS parsing approach adapted from [Supper-Board](https://github.com/fabianxvogt/Supper-Board) (MIT).
- Open Food Facts (ODbL) for packaged products (planned).
- [Apache ECharts](https://echarts.apache.org) 5.5.1 (Apache-2.0), vendored for the dashboard in
  [tools/dashboard/vendor/](tools/dashboard/vendor/README.md).

MIT licensed. Docs index: [docs/README.md](docs/README.md).
