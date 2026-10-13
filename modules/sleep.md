# Module: sleep

**Tracks:** bed time, wake time, quality 1–5, number of wake-ups; from a wearable also duration and
stages (estimates). Knowledge: [../knowledge/sleep.md](../knowledge/sleep.md).

**Check-in handling**
- "Bett 0:30, auf 7:45, schlecht geschlafen, 3× wach" → one `sleep` event with `ts` = wake-up time.
- Only the bedtime in the evening ("Bett 23:30") → `note` with `tags: ["bed"]`; next morning combine it
  with the wake time into the `sleep` event.
- If a device record exists for the same night, keep both; the device values go in `dur_min`/stage
  fields, subjective values stay.

**Review:** mean duration and regularity (bed-time spread), quality vs. last caffeine time, alcohol,
last substance use time, training days, stress. Report candidate links with the number of nights
behind them. Withdrawal from cannabis or nicotine can worsen sleep for 1–3 weeks — say so when a
reduction starts.
