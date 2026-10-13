# Modules

A module = what is tracked, how check-ins handle it, what reviews look at. Active modules are listed
in `me/settings.json` → `modules`. Event fields: [../docs/DATA_FORMAT.md](../docs/DATA_FORMAT.md).

| Module | File | Core events |
|---|---|---|
| `core` (always on) | [core.md](core.md) | `checkin`, `weight`, `symptom`, `note` |
| `sleep` | [sleep.md](sleep.md) | `sleep` |
| `nutrition` | [nutrition.md](nutrition.md) | `meal`, `drink` |
| `pantry` | [pantry-cooking.md](pantry-cooking.md) | pantry events, cookbook |
| `training` | [training.md](training.md) | `training`, `measure` (tests) |
| `substances` | [substances.md](substances.md) | `substance`, `drink` (alcohol, caffeine) |
| `health-checks` | [health-checks.md](health-checks.md) | `measure`, `lab` |
| `devices` | [devices.md](devices.md) | `device` imports into the above |
| `reviews` (always on) | [reviews.md](reviews.md) | reads everything |
