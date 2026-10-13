# Module: health checks

**Tracks:** waist and circumferences, blood pressure, resting heart rate, field tests (walk/run/stair
tests), lab results, doctor visits. Knowledge: [../knowledge/body-metrics-what-and-why.md](../knowledge/body-metrics-what-and-why.md).

**Check-in handling**
- "Bauch 78" → `measure` `metric: waist_cm`. "BD 124/78 Puls 66" → `measure` `metric: bp`.
- Lab results: transcribe values into `lab` events (test, value, unit, reference range, date).
  Raw report files stay optional; do not re-read them unless asked.
- Out-of-range values or red-flag readings → SAFETY.md first.

**Schedule (default):** waist weekly; BP 2 days/week (2 readings morning + evening) once a monitor
exists; circumferences and field test monthly; labs per doctor (≈ yearly).

**Review:** monthly trends; prepare the next doctor visit checklist in `me/doctor/`.
