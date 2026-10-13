# demo-household — synthetic two-person household

**Everything in this folder is fictional.** It mirrors household mode (see
[docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)) in a self-contained layout:

```
demo-household/
├── household/          household.json (members), shared settings, pantry/, recipes/
└── people/
    ├── alex/           consent: true  — the demo-me log, plans and reviews
    └── sam/            consent: false — not onboarded yet, nothing is logged
```

Member paths in `household.json` are relative to the folder that contains `household/`.
In a real setup that is the engine root, and `household/` and `people/` are git-ignored private repos.

```
python3 tools/bos.py --household examples/demo-household/household --today 2026-10-13 profile list
python3 tools/bos.py --household examples/demo-household/household --profile alex --today 2026-10-13 pantry
python3 tools/bos.py --household examples/demo-household/household --today 2026-10-13 dashboard --port 8031
```

Tests copy this folder to a temporary directory and never write into it.
