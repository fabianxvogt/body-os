# Module: core

**Tracks:** morning weight, evening energy/mood/stress (1–5; stress 5 = most stressed), symptoms,
notable events (illness, travel, party) as `note` with tags.

**Check-in handling**
- "70.4" or "Gewicht 70,4" in the morning → `weight`.
- "Energie 3, Laune 4, Stress 2" or "ok day, a bit stressed" → `checkin` (map words to numbers,
  `conf: "med"` when inferred).
- Illness or travel → `note` with tags (`sick`, `travel`, `party`) — reviews exclude or flag these days.
- Lazy-day fallback: a single free-text sentence is fine; extract what you can, don't chase the rest.

**Review:** weight 7-day mean and trend; energy/mood/stress means and their best/worst days with
candidate explanations from other modules.
