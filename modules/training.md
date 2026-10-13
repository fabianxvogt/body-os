# Module: training

**Tracks:** strength sessions (exercises, sets, reps, kg), endurance sessions (duration, distance,
heart rate), effort (RPE), field tests. Plan lives in `me/plans/training.md`.
Knowledge: [../knowledge/strength-training-basics.md](../knowledge/strength-training-basics.md),
[../knowledge/endurance-zone2-and-vo2max.md](../knowledge/endurance-zone2-and-vo2max.md).

**Check-in handling**
- "A erledigt, alles geschafft" → `training` with `plan: "A"` and the planned sets copied from the
  plan's current working weights.
- Deviations ("Bank nur 2×8 bei 40") override the specific sets.
- "30 min gelaufen, locker" → `training` `kind: run`, `dur_min: 30`, plus distance/HR if given.
- Apply the plan's progression rule after each session and update the working-weights table in
  `me/plans/training.md`; tell the user the next targets in one line.

**Review:** sessions done vs planned, progression per main lift, endurance minutes, field-test trend,
missed sessions and why (no guilt — adjust the plan if it doesn't fit life).
