# Module: substances

**Tracks:** tobacco/nicotine, cannabis, alcohol, caffeine, nicotine replacement — counts, times,
triggers. Plan lives in `me/plans/tobacco.md` (or `substances.md`).
Knowledge: [../knowledge/tobacco-nicotine-and-cannabis.md](../knowledge/tobacco-nicotine-and-cannabis.md).

**Check-in handling**
- Shorthand "J 14:30 Pause" → `substance` `kind: joint`, `tobacco: true` (per profile default),
  `trigger: "break"`. "Z" = cigarette, "V" = cannabis vaporizer (`tobacco: false`) — or what
  `me/AGENT.md` defines.
- "3 Joints heute, letzter 23 Uhr" → three events or one with `count: 3`, last one timed.
- Coffee: `drink` `kind: coffee` with time; alcohol: `drink` `kind: alcohol` with `alcohol_units` (and
  `price_eur` when told).
- Pouch/pack: "Pueblo neu auf" → `supply` `item: tobacco`, `action: open`, `g: 30`; "Pueblo leer" →
  `action: empty`. Gives measured grams per day.
- Questionnaires per `settings.questionnaires` (e.g. CUDIT-R at baseline): [../interview/questionnaires/](../interview/questionnaires/README.md).
- Confirm with a count for the day; no comments on single uses during a baseline.

**Coaching rules**
- Non-judgmental. Follow the user's chosen approach and pre-agreed rules (plan B) without reopening
  them outside agreed decision points.
- During a reduction: celebrate streaks factually, treat lapses as data (trigger, time, context),
  re-plan quickly. Watch for sleep/mood dips in the first weeks and explain them.

**Review:** daily counts (total, with tobacco), time of last use vs sleep quality, trigger
distribution, alcohol units/week, caffeine timing; progress against the plan's step.
