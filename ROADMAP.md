# Roadmap

## Now (v0 → v0.1)
- Validate the check-in protocol on a real first two weeks (meal photos, substance shorthand,
  training "A done", pantry purchases).
- Pantry & cooking: purchase summaries, expiry statuses, suggestions with rubrics, cookbook ratings.

## Next
- Device receiver: local HTTP endpoint for an iOS Shortcut / Health Auto Export JSON → events
  (dedupe, best-effort delivery).
- Apple Health `export.zip` importer for history backfill.
- Open Food Facts DE subset for barcoded products.

## Later
- Android Health Connect import.
- USDA FoodData Central source for non-German users.
- Re-interview diff tool (`bos plan diff`).
- Chart generation for monthly reviews.

## Done
- 2026-10-13: readiness fixes — tobacco default for joints, `questionnaire` (PHQ-4, CUDIT-R) and `supply`
  (measured g/day) events, duplicate-id dedupe, first-use time, sync validates and updates the server
  engine, food synonyms.
- 2026-10-13: household comparison — Compare tab (`#vergleich` / `#compare`, household mode only) and
  `GET /api/compare?days=N`: this week's headline per group with a kind leader line, per-group detail
  (grouped bars, values with n, 🏅 lead marker, table view), weekly trends per member; habits and
  progress relative to each member's own plan only (never weight, kcal, body measures, BP, labs);
  consent + `settings.compare.share` gate it, wellbeing and substances are opt-in (substances only
  when every compared member shares them), plan-relative values rank up to 100 % so meeting the plan
  is a tie; demo household now has two consenting members (Alex, Sam) and one without consent (Robin).
- 2026-10-13: home server mode — `bos sync setup|sync` (home-network-only remotes, union merge
  for JSONL), Linux systemd user service, doctor accepts home remotes only.
- 2026-10-13: households and phones — household mode (`household/household.json`, shared pantry,
  cookbook, shopping list and kitchen settings; `bos household init` moves the kitchen without
  overwriting; `bos profile add|list|consent`; `--profile`, `--household`), consent gate (no events
  for members who have not agreed; onboarding card in the dashboard), profile chooser and avatar menu,
  household kitchen view, `bos dashboard --lan` with household key (cookie via one-time device link,
  401 otherwise, loopback-only `/devices` QR page, Host allow-list, `--rotate-key`), PWA manifest and
  generated icons, safe-area layout, `bos service install|uninstall|status` (macOS launchd), hooks and
  `.gitignore` for `people/` and `household/`, `examples/demo-household/`.
- 2026-10-13: multi-tab dashboard (hash routes `#heute` … `#journal`, English aliases): phase banner,
  check-in checklist, due today (training schedule, measurements, weekly review), week focus from the
  latest review; weight goal corridor, circumferences, ESH blood-pressure zones, labs; protein band
  from g/kg goals, protein per meal, macro split, meal timing, protein sources; pantry filters, expiry
  agenda, grocery/eating-out spend, food waste, shopping list, cuisine variety, learning path; sleep
  window and regularity, sleep factors; tobacco baseline, streaks, plan-B check; training calendar,
  e1RM, volume, endurance pace, field tests, next goals; review viewer (`/api/review`), notes timeline,
  decisions; generic cost model (`settings.costs`, `price_eur`) with monthly spending.
- 2026-10-13: custom local dashboard (`bos dashboard`): weight trend, protein/kcal vs. targets, sleep
  vs. last substance time, triggers and habit-time heatmap, check-ins, training vs. plan, strength,
  body measures, pantry expiry, cookbook; live from `me/`, 127.0.0.1 only, vendored ECharts, light/dark,
  table views, English/German.
- 2026-10-13: v0 — agent manual, safety rules, interview catalog, modules, data format,
  `bos` CLI with tests, BLS 4.0 import, demo persona, privacy git hooks, knowledge pages.
