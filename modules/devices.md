# Module: devices

**Purpose:** get wearable/phone data into `me/` without cloud services where possible.

| Route | Cost | Notes |
|---|---|---|
| Manual Apple Health export (`export.zip`) → `me/inbox/` | free | one-time history backfill or every 1–2 weeks |
| iOS Shortcut ("Find Health Samples" → POST JSON to a receiver on the Mac in the home Wi-Fi) | free | Health data is unreadable while the phone is locked — trigger on a morning action (alarm off, app open) |
| Health Auto Export (paid iOS app) → same receiver | ~25 USD once | more reliable background sync; still best-effort, dedupe needed |
| Android: Health Connect export | free | planned |

Imported values become normal events with `src: "device"` (sleep duration/stages, resting HR, HRV,
steps, workouts, VO2max estimate, BP from connected cuffs). Device sleep stages, HRV and VO2max are
estimates — trends matter more than single values.

**Status:** receiver and importers are on the [roadmap](../ROADMAP.md); until then, the agent can
read an export file placed in `me/inbox/` on request.
