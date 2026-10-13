# demo-me — synthetic example instance

**Everything in this folder is fictional and generated for tests and demos.** "Demo Person" does not
exist; no value here comes from a real person.

It mirrors the layout of a private `me/` folder (see [docs/DATA_FORMAT.md](../../docs/DATA_FORMAT.md)):
14 days of log events (2026-09-30 to 2026-10-13) covering every event type, a pantry history that
produces every derived status (`ok`, `soon`, `check`, `discard`, `gone`) on 2026-10-13, and a small
cookbook.

Try it (pin "today" so the output does not drift):

```
python3 tools/bos.py --me examples/demo-me --today 2026-10-13 summary --days 14
python3 tools/bos.py --me examples/demo-me --today 2026-10-13 pantry --all
python3 tools/bos.py --me examples/demo-me --data /tmp/demo-data --today 2026-10-13 build
```

Tests copy this folder to a temporary directory and never write into it.
