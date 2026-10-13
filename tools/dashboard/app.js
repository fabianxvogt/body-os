/* body-os dashboard — vanilla JS, no build step, no external requests.
 * Data: GET /api/data?days=14|30|90|all (rebuilt live from me/ on every request, grouped by tab —
 * see tools/bos.py dashboard_data) and GET /api/review?file=… for review markdown.
 * Charts: Apache ECharts (vendor/, Apache-2.0). Colours come from CSS custom properties in style.css
 * so light/dark stay one system. Tabs are hash routes; each tab is built and charted lazily the first
 * time it becomes visible, and its charts are resized whenever it is shown again. */
(function () {
  "use strict";

  // ------------------------------------------------------------------------------------------
  // i18n
  // ------------------------------------------------------------------------------------------

  var I18N = {
    en: {
      locale: "en-GB", days: "days", all: "All", period: "Period", updated: "updated", local_only: "local only",
      theme_dark: "Switch to dark theme", theme_light: "Switch to light theme", tabs_label: "Sections",
      table: "Table", chart: "Chart", empty: "No data yet – arrives with your first check-in",
      empty_period: "Nothing in this period", load_error: "Could not load data",
      no_entries: "No entries in this period yet.", no_entries_hint: "Log a check-in with your agent and reload this page.",
      day: "Day", week: "Week", wk: "W", month: "Month", total: "Total", none: "none", more: "more", less: "less",
      hypothesis: "{n} nights · hypothesis, not proof", n_nights: "{n} nights", latest: "latest", previous: "previous",
      setting_hint: "Add {key} in settings.json", ago_today: "today", in_days: "in {n} days", days_ago: "{n} days ago",
      tomorrow: "tomorrow", overdue: "overdue", done: "done", open: "open", due: "due", est: "≈ estimate",
      tab: {
        today: "Today", body: "Body", nutrition: "Nutrition", kitchen: "Kitchen", sleep: "Sleep & energy",
        substances: "Substances", training: "Training", journal: "Journal"
      },
      q: {
        today: "Where do I stand today, and what is still missing?",
        body: "Is my body moving in the planned direction?",
        nutrition: "Am I eating enough protein – and what, when and how much?",
        kitchen: "What needs using up, what is missing, and what do I cook?",
        sleep: "How long and how regularly do I sleep – and what goes along with it?",
        substances: "How is my use developing against the baseline?",
        training: "Am I training as planned, and getting stronger?",
        journal: "What did I note, review and decide?"
      },
      // today
      phase: "Current phase", phase_day: "Day {x} of {y}", phase_day_open: "Day {x}", no_phase: "No phase planned",
      no_phase_hint: "Add phases in settings.json (phases) to see where you are in your plan.",
      next_decision: "Next decision", no_decision: "No open decision",
      focus: "Focus of the week", focus_from: "from {file}", no_focus: "No weekly focus yet",
      no_focus_hint: "Appears after your first weekly review with a “Focus” section.",
      checklist: "Today’s check-in", checklist_sub: "{done} of {n} logged",
      ck: { weight: "Weight", sleep: "Sleep", meal: "Meals", checkin: "Check-in", drink: "Drinks", training: "Training",
        note: "Note", substance: "Substances", measure: "Measurement", symptom: "Symptom", lab: "Lab" },
      ck_meals: "{n} (min. {m})", ck_subs: "Substances today", ck_subs_val: "{n} · last {t}", ck_subs_none: "none so far",
      due_today: "Due today", nothing_due: "Nothing scheduled for today",
      due_training: "Training: {what}", next_training: "Next training: {day} · {what}",
      due_review: "Weekly review", this_week: "{n} of {m} this week",
      what: { strength: "strength", endurance: "endurance", other: "other", run: "run", bike: "bike", walk: "walk" },
      measure_names: { waist_cm: "Waist", circumferences: "Circumferences", bp: "Blood pressure", resting_hr: "Resting HR",
        arm_cm: "Arm", chest_cm: "Chest", thigh_cm: "Thigh", hrv_ms: "HRV", vo2max: "VO₂max", weight: "Weight" },
      pantry_alerts: "Kitchen alerts", pantry_alerts_none: "Nothing urgent in the pantry", to_kitchen: "Open kitchen",
      kpis: "Key figures", kpis_sub: "selected period",
      spend: "Spending this month", spend_sub: "{from} – {to}", to_details: "Details",
      spend_none: "No prices logged this month", spend_hint: "Add price_eur to purchases, meals out or drinks; set costs in settings.json for estimates.",
      spend_unknown: "{n} entries without a price",
      cost: { groceries: "Groceries", out: "Eating & drinking out", tobacco: "Tobacco", cannabis: "Cannabis",
        alcohol: "Alcohol", coffee: "Coffee" },
      kpi_weight: "Weight", kpi_weight_sub_delta: "vs. 7 days ago", kpi_weight_sub: "7-day mean",
      kpi_protein: "Protein Ø / day", kpi_protein_target: "target", kpi_protein_sub: "on days with meals",
      kpi_sleep: "Sleep Ø", kpi_sleep_q: "quality Ø", kpi_use: "Use / day", kpi_joint: "Joints / day",
      kpi_cigarette: "Cigarettes / day", kpi_tobacco: "with tobacco Ø", kpi_prev: "vs. previous",
      kpi_train: "Training this week", kpi_train_sub: "of {n} planned",
      // body
      sec_weight: "Weight", weight: "Weight", weight_sub: "kg · daily weigh-in, 7-day mean and goal corridor",
      daily: "Daily", avg7: "7-day mean", corridor: "Goal corridor",
      corridor_note: "Corridor {lo} to {hi} kg/month from {kg} kg on {day}",
      corridor_hint: "Set goals.weight_rate_kg_month in settings.json to see a goal corridor.",
      sec_circ: "Circumferences", sec_circ_sub: "cm · one chart per measure",
      sec_heart: "Blood pressure & heart", bp: "Blood pressure", bp_sub: "mmHg · systolic and diastolic",
      sys: "Systolic", dia: "Diastolic", pulse: "Pulse",
      bp_cat: { optimal: "optimal", normal: "normal", high_normal: "high-normal", hypertension: "hypertension range" },
      bp_legend: "ESH categories: optimal <120/80 · normal 120–129/80–84 · high-normal 130–139/85–89 · hypertension ≥140/90",
      bp_note: "Single readings vary; categories describe averages and are not a diagnosis.",
      vit: { resting_hr: "Resting heart rate", hrv_ms: "Heart-rate variability", vo2max: "VO₂max" },
      vit_unit: { resting_hr: "bpm", hrv_ms: "ms", vo2max: "ml/kg/min" },
      labs: "Lab values", labs_sub: "latest value per test, with reference range", test: "Test", value: "Value",
      ref: "Reference", status: "Status", date: "Date", lab_in: "in range", lab_low: "below range", lab_high: "above range",
      no_period_value: "No measurement in this period · latest {v} on {d}",
      // nutrition
      sec_intake: "Intake", protein: "Protein per day", protein_sub: "g · band = target", target: "Target",
      protein_basis: "{lo}–{hi} g/kg × {kg} kg", kcal: "Calories per day", kcal_sub: "kcal · logged meals",
      slots: "Protein per meal", slots_sub: "g · stacked by meal",
      slot: { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner", snack: "Snack", other: "Other" },
      macros: "Macro split", macros_sub: "share of kcal from protein, carbs and fat · Ø per day with meals",
      macro: { protein_g: "Protein", carbs_g: "Carbs", fat_g: "Fat" }, per_day: "per day", share: "kcal share",
      timing: "Meal timing", timing_sub: "each dot is a meal · time of day",
      sources: "Top protein sources", sources_sub: "g protein in the period · from item-level values",
      sources_hint: "Log items[].protein_g per meal item to see your protein sources.",
      sec_drinks: "Drinks", water: "Water", water_sub: "litres per day", coffee: "Coffee", coffee_sub: "caffeinated drinks per day",
      last_coffee: "Last coffee", last_coffee_sub: "time of the day’s last caffeinated drink", last: "last",
      alcohol: "Alcohol", alcohol_sub: "units per week (1 unit = 10 g ethanol)", units: "Units",
      completeness: "Logging completeness", days_2meals: "days with ≥ 2 meals", meals_no_kcal: "meals without kcal",
      meals_logged: "meals logged",
      // kitchen
      sec_pantry: "Pantry", pantry: "Pantry", pantry_sub: "most urgent first", item: "Item", left: "Left",
      storage: "Storage", expiry: "Expiry", all_storage: "All",
      status_discard: "discard", status_check: "check", status_soon: "soon", status_ok: "ok",
      days_left: "{n} d left", days_past: "{n} d past", today: "today", no_date: "no date", opened: "opened",
      estimated: "estimated", fridge: "Fridge", freezer: "Freezer", pantry_store: "Cupboard",
      timeline: "Expiry next 7 days", timeline_sub: "per day · overdue first", timeline_none: "Nothing expires in the next 7 days",
      sec_money: "Spending", spend_week: "Groceries per week", spend_week_sub: "€ · from purchases with prices",
      spend_store: "Groceries per store", spend_store_sub: "€ in the period", prices_hint: "Record price_eur on purchase items to see spending.",
      eating_out: "Eating & drinking out", eating_out_sub: "€ per week · meals and drinks with price_eur",
      eating_out_hint: "Add price_eur to meals or drinks bought out.",
      waste: "Food waste", waste_sub: "€ per month · price × share left when discarded", waste_items: "Discarded",
      waste_none: "Nothing discarded yet", reason: { expired: "expired", spoiled: "spoiled", other: "other" },
      shopping: "Shopping list", shopping_hint: "Your agent writes pantry/shopping-list.md at the weekly review.",
      sec_cook: "Cooking", cookbook: "Cookbook", cookbook_sub: "last cooked and suggested", simplicity: "Simplicity",
      nutrition_score: "Nutrition", rating: "Rating", suggested: "suggested", cooked: "cooked",
      cuisines: "Cuisine variety", cuisines_sub: "cooked dishes per cuisine · last 30 days", dishes: "Dishes",
      skills: "Learning path", skills_sub: "techniques learned while cooking", skills_count: "{n} techniques",
      skills_hint: "Recipes with a skill field appear here once cooked.", ratings: "{up} liked · {down} not liked",
      // sleep
      sec_sleep: "Sleep", sleep: "Sleep", sleep_sub: "hours per night · line at 7 h", hours: "Hours",
      window: "Bed and wake times", window_sub: "each bar is one night · 20:00 to 12:00", bed: "Bed", wake: "Wake",
      regularity_t: "Regularity", bed_mean: "Ø bedtime", wake_mean: "Ø wake time", bed_sd: "bedtime spread (SD)",
      regularity_note: "Smaller spread = more regular rhythm.", quality: "Sleep quality", quality_sub: "1–5",
      wakeups: "Wake-ups", wakeups_sub: "per night",
      sec_factors: "What goes along with sleep", sec_factors_sub: "small samples · hypotheses, not proof",
      svu: "Last use the evening before", svu_sub: "time of last use after 18:00 → hours slept",
      svu_use: "Use in the evening", svu_none: "No evening use", last_use: "Last use", no_use: "nothing after 18:00",
      vs_coffee: "Last coffee the day before", vs_coffee_sub: "time → hours slept",
      vs_alcohol: "Alcohol the day before", vs_alcohol_sub: "Ø hours slept", no_alcohol: "No alcohol", some_alcohol: "Alcohol",
      vs_training: "Training day vs. rest day", vs_training_sub: "Ø hours slept the following night",
      rest_day: "Rest day", training_day: "Training day", mean_sleep: "Ø sleep",
      sec_mind: "Energy & mood", mind: "Energy, mood, stress", mind_sub: "check-ins 1–5 · stress 5 = high",
      energy: "Energy", mood: "Mood", stress: "Stress",
      // substances
      sec_progress: "Progress", free_days: "Tobacco-free days", free_days_sub: "of {n} logged days in the period",
      streak: "Current streak", streak_longest: "Longest streak", streak_unit: "days",
      baseline: "Baseline", baseline_sub: "tobacco uses / day in {name}", per_day_unit: "/ day",
      planb: "Plan-B check", planb_sub: "{name} · day {d} of {w}", planb_now: "Last {n} full days",
      planb_of: "of baseline", planb_thr: "Plan B is discussed when ≥ {t} % after {w} days",
      planb_status: { on_track: "on track", watch: "keep watching", plan_b_due: "Plan B due – discuss it" },
      planb_wait: "Starts with the first full day of the phase.",
      tob: "With vs. without tobacco", tob_sub: "uses per day · lines = baseline and phase target",
      with_tob: "with tobacco", without_tob: "without tobacco", phase_target: "Target",
      trig: "Use per day by trigger", trig_sub: "count · stacked by trigger", other: "Other",
      first_use: "First use of the day", first_use_sub: "time of day · higher = later in the day", first: "First use",
      heat: "Use times", heat_sub: "weekday × hour · darker = more often",
      weekdays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], uses: "×", hour: "Hour",
      share: "Trigger share", share_sub: "share of all uses in the period",
      sec_costs: "Costs", costs_month: "Cost per month", costs_month_sub: "€ · ≈ estimated from settings.costs",
      costs_week: "Cost per week", costs_week_sub: "€ in the period", saved: "Saved since {name}",
      saved_sub: "(baseline {b} − now {c} per day) × {n} days × {p} per use", costs_hint: "Set {keys} in settings.json (costs) to see costs.",
      substances_inactive: "The substances module is not active.", tobacco: "with tobacco",
      // training
      sec_sessions: "Sessions", calendar: "Training calendar", calendar_sub: "last weeks · colour = type",
      cat: { strength: "Strength", endurance: "Endurance", other: "Other" },
      train: "Sessions per week", train_sub: "sessions · dashed line = plan", plan: "Plan", sessions: "Sessions",
      minutes: "Minutes", sec_strength: "Strength", lifts: "Estimated 1RM", lifts_sub: "kg · Epley from the top set per session",
      e1rm: "e1RM", top_set: "Top set", others: "Also logged", volume: "Weekly volume", volume_sub: "kg · sets × reps × weight",
      sec_endurance: "Endurance", end_min: "Endurance minutes", end_min_sub: "minutes per week", pace: "Pace per session",
      pace_sub: "min/km · lower = faster", avg_hr: "Ø heart rate", avg_hr_sub: "bpm per session", distance: "Distance",
      tests: "Field tests", next_goals: "Next goals", next_goals_sub: "working weights from plans/training.json",
      exercise: "Exercise", sets_reps: "Sets × reps", working: "Working kg", next_kg: "Next", last_logged: "Last logged",
      goals_hint: "Your agent keeps plans/training.json with current working weights.",
      // journal
      reviews: "Reviews", reviews_sub: "weekly and monthly, newest first", weekly: "weekly", monthly: "monthly",
      reviews_none: "No reviews yet", reviews_hint: "Weekly reviews appear in reviews/ after your first review.",
      timeline_j: "Notes & symptoms", timeline_j_sub: "newest first · in the selected period",
      type: { note: "Note", symptom: "Symptom", meal: "Meal", drink: "Drink", substance: "Substance", training: "Training",
        sleep: "Sleep", weight: "Weight", checkin: "Check-in", measure: "Measurement", lab: "Lab" },
      severity: "severity {n}/5", decisions: "Decisions", decisions_sub: "from settings.json",
      decisions_hint: "Add decisions to settings.json to track them here.",
      foot_live: "Live from me/ on every reload · nothing leaves this machine", foot_raw: "Raw tables: bos dash",
      foot_credit: "Charts: Apache ECharts 5.5.1 (Apache-2.0)",
      triggers: { "?": "unknown", "after-meal": "after meal" }
    },
    de: {
      locale: "de-DE", days: "Tage", all: "Alles", period: "Zeitraum", updated: "aktualisiert", local_only: "nur lokal",
      theme_dark: "Dunkles Design", theme_light: "Helles Design", tabs_label: "Bereiche",
      table: "Tabelle", chart: "Diagramm", empty: "Noch keine Daten – kommt mit deinem ersten Check-in",
      empty_period: "Nichts in diesem Zeitraum", load_error: "Daten konnten nicht geladen werden",
      no_entries: "Noch keine Einträge in diesem Zeitraum.", no_entries_hint: "Mach einen Check-in mit deinem Agenten und lade die Seite neu.",
      day: "Tag", week: "Woche", wk: "KW ", month: "Monat", total: "Gesamt", none: "keiner", more: "mehr", less: "weniger",
      hypothesis: "{n} Nächte · Hypothese, kein Beweis", n_nights: "{n} Nächte", latest: "zuletzt", previous: "davor",
      setting_hint: "{key} in settings.json eintragen", ago_today: "heute", in_days: "in {n} Tagen", days_ago: "vor {n} Tagen",
      tomorrow: "morgen", overdue: "überfällig", done: "erledigt", open: "offen", due: "fällig", est: "≈ geschätzt",
      tab: {
        today: "Heute", body: "Körper", nutrition: "Ernährung", kitchen: "Küche", sleep: "Schlaf & Energie",
        substances: "Konsum", training: "Training", journal: "Journal"
      },
      q: {
        today: "Wo stehe ich heute, und was fehlt noch?",
        body: "Bewegt sich mein Körper in die geplante Richtung?",
        nutrition: "Esse ich genug Protein – und was, wann und wie viel?",
        kitchen: "Was muss weg, was fehlt, und was koche ich?",
        sleep: "Wie lange und wie regelmäßig schlafe ich – und was hängt damit zusammen?",
        substances: "Wie entwickelt sich mein Konsum gegenüber der Baseline?",
        training: "Trainiere ich nach Plan, und werde ich stärker?",
        journal: "Was habe ich notiert, ausgewertet und entschieden?"
      },
      phase: "Aktuelle Phase", phase_day: "Tag {x} von {y}", phase_day_open: "Tag {x}", no_phase: "Keine Phase geplant",
      no_phase_hint: "Phasen in settings.json (phases) eintragen, um zu sehen, wo du im Plan stehst.",
      next_decision: "Nächste Entscheidung", no_decision: "Keine offene Entscheidung",
      focus: "Fokus der Woche", focus_from: "aus {file}", no_focus: "Noch kein Wochenfokus",
      no_focus_hint: "Erscheint nach dem ersten Wochenreview mit einem Abschnitt „Fokus“.",
      checklist: "Check-in heute", checklist_sub: "{done} von {n} erfasst",
      ck: { weight: "Gewicht", sleep: "Schlaf", meal: "Mahlzeiten", checkin: "Befinden", drink: "Getränke", training: "Training",
        note: "Notiz", substance: "Konsum", measure: "Messung", symptom: "Symptom", lab: "Labor" },
      ck_meals: "{n} (min. {m})", ck_subs: "Konsum heute", ck_subs_val: "{n} · zuletzt {t}", ck_subs_none: "bisher keiner",
      due_today: "Heute fällig", nothing_due: "Heute ist nichts geplant",
      due_training: "Training: {what}", next_training: "Nächstes Training: {day} · {what}",
      due_review: "Wochenreview", this_week: "{n} von {m} diese Woche",
      what: { strength: "Kraft", endurance: "Ausdauer", other: "Sonstiges", run: "Laufen", bike: "Rad", walk: "Gehen" },
      measure_names: { waist_cm: "Bauchumfang", circumferences: "Umfänge", bp: "Blutdruck", resting_hr: "Ruhepuls",
        arm_cm: "Arm", chest_cm: "Brust", thigh_cm: "Oberschenkel", hrv_ms: "HRV", vo2max: "VO₂max", weight: "Gewicht" },
      pantry_alerts: "Küche", pantry_alerts_none: "Im Vorrat ist nichts dringend", to_kitchen: "Zur Küche",
      kpis: "Kennzahlen", kpis_sub: "gewählter Zeitraum",
      spend: "Ausgaben diesen Monat", spend_sub: "{from} – {to}", to_details: "Details",
      spend_none: "Diesen Monat keine Preise erfasst", spend_hint: "price_eur bei Einkäufen, Essen unterwegs oder Getränken erfassen; für Schätzungen costs in settings.json setzen.",
      spend_unknown: "{n} Einträge ohne Preis",
      cost: { groceries: "Lebensmittel", out: "Essen/Trinken unterwegs", tobacco: "Tabak", cannabis: "Cannabis",
        alcohol: "Alkohol", coffee: "Kaffee" },
      kpi_weight: "Gewicht", kpi_weight_sub_delta: "vs. vor 7 Tagen", kpi_weight_sub: "7-Tage-Schnitt",
      kpi_protein: "Protein Ø / Tag", kpi_protein_target: "Ziel", kpi_protein_sub: "an Tagen mit Mahlzeiten",
      kpi_sleep: "Schlaf Ø", kpi_sleep_q: "Qualität Ø", kpi_use: "Konsum / Tag", kpi_joint: "Joints / Tag",
      kpi_cigarette: "Zigaretten / Tag", kpi_tobacco: "davon mit Tabak Ø", kpi_prev: "vs. Vorperiode",
      kpi_train: "Training diese Woche", kpi_train_sub: "von {n} geplant",
      sec_weight: "Gewicht", weight: "Gewicht", weight_sub: "kg · Tageswert, 7-Tage-Schnitt und Zielkorridor",
      daily: "Tageswert", avg7: "7-Tage-Schnitt", corridor: "Zielkorridor",
      corridor_note: "Korridor {lo} bis {hi} kg/Monat ab {kg} kg am {day}",
      corridor_hint: "goals.weight_rate_kg_month in settings.json eintragen, um einen Zielkorridor zu sehen.",
      sec_circ: "Umfänge", sec_circ_sub: "cm · ein Diagramm pro Maß",
      sec_heart: "Blutdruck & Herz", bp: "Blutdruck", bp_sub: "mmHg · systolisch und diastolisch",
      sys: "Systolisch", dia: "Diastolisch", pulse: "Puls",
      bp_cat: { optimal: "optimal", normal: "normal", high_normal: "hoch-normal", hypertension: "Hypertonie-Bereich" },
      bp_legend: "ESH-Kategorien: optimal <120/80 · normal 120–129/80–84 · hoch-normal 130–139/85–89 · Hypertonie ≥140/90",
      bp_note: "Einzelmessungen schwanken; Kategorien beschreiben Mittelwerte und sind keine Diagnose.",
      vit: { resting_hr: "Ruhepuls", hrv_ms: "Herzratenvariabilität", vo2max: "VO₂max" },
      vit_unit: { resting_hr: "Schläge/min", hrv_ms: "ms", vo2max: "ml/kg/min" },
      labs: "Laborwerte", labs_sub: "letzter Wert pro Test, mit Referenzbereich", test: "Test", value: "Wert",
      ref: "Referenz", status: "Status", date: "Datum", lab_in: "im Bereich", lab_low: "unter Referenz", lab_high: "über Referenz",
      no_period_value: "Keine Messung in diesem Zeitraum · zuletzt {v} am {d}",
      sec_intake: "Aufnahme", protein: "Protein pro Tag", protein_sub: "g · Band = Ziel", target: "Ziel",
      protein_basis: "{lo}–{hi} g/kg × {kg} kg", kcal: "Kalorien pro Tag", kcal_sub: "kcal · geloggte Mahlzeiten",
      slots: "Protein pro Mahlzeit", slots_sub: "g · gestapelt nach Mahlzeit",
      slot: { breakfast: "Frühstück", lunch: "Mittag", dinner: "Abend", snack: "Snack", other: "Sonstige" },
      macros: "Makro-Verteilung", macros_sub: "Anteil der kcal aus Protein, Kohlenhydraten und Fett · Ø pro Tag mit Mahlzeiten",
      macro: { protein_g: "Protein", carbs_g: "Kohlenhydrate", fat_g: "Fett" }, per_day: "pro Tag", share: "kcal-Anteil",
      timing: "Essenszeiten", timing_sub: "jeder Punkt ist eine Mahlzeit · Uhrzeit",
      sources: "Top-Proteinquellen", sources_sub: "g Protein im Zeitraum · aus Werten pro Zutat",
      sources_hint: "items[].protein_g pro Zutat loggen, um deine Proteinquellen zu sehen.",
      sec_drinks: "Getränke", water: "Wasser", water_sub: "Liter pro Tag", coffee: "Kaffee", coffee_sub: "koffeinhaltige Getränke pro Tag",
      last_coffee: "Letzter Kaffee", last_coffee_sub: "Uhrzeit des letzten koffeinhaltigen Getränks", last: "zuletzt",
      alcohol: "Alkohol", alcohol_sub: "Einheiten pro Woche (1 Einheit = 10 g Alkohol)", units: "Einheiten",
      completeness: "Vollständigkeit", days_2meals: "Tage mit ≥ 2 Mahlzeiten", meals_no_kcal: "Mahlzeiten ohne kcal",
      meals_logged: "Mahlzeiten erfasst",
      sec_pantry: "Vorrat", pantry: "Bestand", pantry_sub: "dringendstes zuerst", item: "Artikel", left: "Rest",
      storage: "Lagerort", expiry: "Haltbarkeit", all_storage: "Alle",
      status_discard: "wegwerfen", status_check: "prüfen", status_soon: "bald", status_ok: "ok",
      days_left: "noch {n} T.", days_past: "{n} T. drüber", today: "heute", no_date: "ohne Datum", opened: "offen",
      estimated: "geschätzt", fridge: "Kühlschrank", freezer: "Gefrierfach", pantry_store: "Vorrat",
      timeline: "Ablauf in den nächsten 7 Tagen", timeline_sub: "pro Tag · Überfälliges zuerst", timeline_none: "In den nächsten 7 Tagen läuft nichts ab",
      sec_money: "Ausgaben", spend_week: "Lebensmittel pro Woche", spend_week_sub: "€ · aus Einkäufen mit Preis",
      spend_store: "Lebensmittel pro Laden", spend_store_sub: "€ im Zeitraum", prices_hint: "price_eur bei Einkaufsartikeln erfassen, um Ausgaben zu sehen.",
      eating_out: "Essen & Trinken unterwegs", eating_out_sub: "€ pro Woche · Mahlzeiten und Getränke mit price_eur",
      eating_out_hint: "price_eur bei auswärts gekauften Mahlzeiten oder Getränken erfassen.",
      waste: "Lebensmittelverschwendung", waste_sub: "€ pro Monat · Preis × Restanteil beim Wegwerfen", waste_items: "Weggeworfen",
      waste_none: "Noch nichts weggeworfen", reason: { expired: "abgelaufen", spoiled: "verdorben", other: "sonstiges" },
      shopping: "Einkaufsliste", shopping_hint: "Dein Agent schreibt pantry/shopping-list.md beim Wochenreview.",
      sec_cook: "Kochen", cookbook: "Kochbuch", cookbook_sub: "zuletzt gekocht und vorgeschlagen", simplicity: "Einfachheit",
      nutrition_score: "Nährwert", rating: "Bewertung", suggested: "vorgeschlagen", cooked: "gekocht",
      cuisines: "Küchen-Vielfalt", cuisines_sub: "gekochte Gerichte pro Küche · letzte 30 Tage", dishes: "Gerichte",
      skills: "Lernpfad", skills_sub: "beim Kochen gelernte Techniken", skills_count: "{n} Techniken",
      skills_hint: "Rezepte mit skill-Feld erscheinen hier, sobald sie gekocht sind.", ratings: "{up} gemocht · {down} nicht gemocht",
      sec_sleep: "Schlaf", sleep: "Schlaf", sleep_sub: "Stunden pro Nacht · Linie bei 7 h", hours: "Stunden",
      window: "Bett- und Aufstehzeiten", window_sub: "jeder Balken ist eine Nacht · 20:00 bis 12:00", bed: "Bett", wake: "Auf",
      regularity_t: "Regelmäßigkeit", bed_mean: "Ø Bettzeit", wake_mean: "Ø Aufstehen", bed_sd: "Streuung der Bettzeit (SD)",
      regularity_note: "Kleinere Streuung = regelmäßigerer Rhythmus.", quality: "Schlafqualität", quality_sub: "1–5",
      wakeups: "Wachphasen", wakeups_sub: "pro Nacht",
      sec_factors: "Was mit dem Schlaf zusammenhängt", sec_factors_sub: "kleine Stichproben · Hypothesen, kein Beweis",
      svu: "Letzter Konsum am Vorabend", svu_sub: "Uhrzeit des letzten Konsums nach 18 Uhr → Schlafdauer",
      svu_use: "Konsum am Abend", svu_none: "Kein Konsum am Abend", last_use: "Letzter Konsum", no_use: "nichts nach 18 Uhr",
      vs_coffee: "Letzter Kaffee am Vortag", vs_coffee_sub: "Uhrzeit → Schlafdauer",
      vs_alcohol: "Alkohol am Vortag", vs_alcohol_sub: "Ø Schlafdauer", no_alcohol: "Kein Alkohol", some_alcohol: "Alkohol",
      vs_training: "Trainingstag vs. Ruhetag", vs_training_sub: "Ø Schlafdauer in der folgenden Nacht",
      rest_day: "Ruhetag", training_day: "Trainingstag", mean_sleep: "Ø Schlaf",
      sec_mind: "Energie & Stimmung", mind: "Energie, Stimmung, Stress", mind_sub: "Check-ins 1–5 · Stress 5 = hoch",
      energy: "Energie", mood: "Stimmung", stress: "Stress",
      sec_progress: "Fortschritt", free_days: "Tabakfreie Tage", free_days_sub: "von {n} erfassten Tagen im Zeitraum",
      streak: "Aktuelle Serie", streak_longest: "Längste Serie", streak_unit: "Tage",
      baseline: "Baseline", baseline_sub: "Tabak-Konsum / Tag in {name}", per_day_unit: "/ Tag",
      planb: "Plan-B-Check", planb_sub: "{name} · Tag {d} von {w}", planb_now: "Letzte {n} vollen Tage",
      planb_of: "der Baseline", planb_thr: "Plan B wird besprochen bei ≥ {t} % nach {w} Tagen",
      planb_status: { on_track: "im Plan", watch: "weiter beobachten", plan_b_due: "Plan B fällig – besprechen" },
      planb_wait: "Beginnt mit dem ersten vollen Tag der Phase.",
      tob: "Mit vs. ohne Tabak", tob_sub: "Konsum pro Tag · Linien = Baseline und Phasenziel",
      with_tob: "mit Tabak", without_tob: "ohne Tabak", phase_target: "Ziel",
      trig: "Konsum pro Tag nach Auslöser", trig_sub: "Anzahl · gestapelt nach Auslöser", other: "Sonstiges",
      first_use: "Erster Konsum des Tages", first_use_sub: "Uhrzeit · höher = später am Tag", first: "Erster Konsum",
      heat: "Konsum-Uhrzeiten", heat_sub: "Wochentag × Stunde · dunkler = häufiger",
      weekdays: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], uses: "×", hour: "Stunde",
      share: "Anteil der Auslöser", share_sub: "Anteil an allem Konsum im Zeitraum",
      sec_costs: "Kosten", costs_month: "Kosten pro Monat", costs_month_sub: "€ · ≈ geschätzt aus settings.costs",
      costs_week: "Kosten pro Woche", costs_week_sub: "€ im Zeitraum", saved: "Gespart seit {name}",
      saved_sub: "(Baseline {b} − jetzt {c} pro Tag) × {n} Tage × {p} pro Konsum", costs_hint: "{keys} in settings.json (costs) eintragen, um Kosten zu sehen.",
      substances_inactive: "Das Modul Konsum ist nicht aktiv.", tobacco: "mit Tabak",
      sec_sessions: "Einheiten", calendar: "Trainingskalender", calendar_sub: "letzte Wochen · Farbe = Art",
      cat: { strength: "Kraft", endurance: "Ausdauer", other: "Sonstiges" },
      train: "Einheiten pro Woche", train_sub: "Einheiten · gestrichelt = Plan", plan: "Plan", sessions: "Einheiten",
      minutes: "Minuten", sec_strength: "Kraft", lifts: "Geschätztes 1RM", lifts_sub: "kg · Epley aus dem schwersten Satz pro Einheit",
      e1rm: "e1RM", top_set: "Schwerster Satz", others: "Außerdem geloggt", volume: "Wochenvolumen", volume_sub: "kg · Sätze × Wdh. × Gewicht",
      sec_endurance: "Ausdauer", end_min: "Ausdauer-Minuten", end_min_sub: "Minuten pro Woche", pace: "Pace pro Einheit",
      pace_sub: "min/km · niedriger = schneller", avg_hr: "Ø Herzfrequenz", avg_hr_sub: "Schläge/min pro Einheit", distance: "Distanz",
      tests: "Feldtests", next_goals: "Nächste Ziele", next_goals_sub: "Arbeitsgewichte aus plans/training.json",
      exercise: "Übung", sets_reps: "Sätze × Wdh.", working: "Arbeits-kg", next_kg: "Nächstes", last_logged: "Zuletzt geloggt",
      goals_hint: "Dein Agent pflegt plans/training.json mit den aktuellen Arbeitsgewichten.",
      reviews: "Reviews", reviews_sub: "wöchentlich und monatlich, neueste zuerst", weekly: "Woche", monthly: "Monat",
      reviews_none: "Noch keine Reviews", reviews_hint: "Wochenreviews erscheinen in reviews/ nach deinem ersten Review.",
      timeline_j: "Notizen & Symptome", timeline_j_sub: "neueste zuerst · im gewählten Zeitraum",
      type: { note: "Notiz", symptom: "Symptom", meal: "Mahlzeit", drink: "Getränk", substance: "Konsum", training: "Training",
        sleep: "Schlaf", weight: "Gewicht", checkin: "Befinden", measure: "Messung", lab: "Labor" },
      severity: "Stärke {n}/5", decisions: "Entscheidungen", decisions_sub: "aus settings.json",
      decisions_hint: "Entscheidungen in settings.json eintragen, um sie hier zu verfolgen.",
      foot_live: "Live aus me/ bei jedem Neuladen · nichts verlässt diesen Rechner", foot_raw: "Rohdaten-Tabellen: bos dash",
      foot_credit: "Charts: Apache ECharts 5.5.1 (Apache-2.0)",
      triggers: {
        "?": "unbekannt", stress: "Stress", boredom: "Langeweile", "after-meal": "nach dem Essen",
        "break": "Pause", evening: "Abend", social: "sozial", habit: "Gewohnheit", craving: "Verlangen"
      }
    }
  };

  var T = I18N.en;
  var TABS = [
    { id: "today", de: "heute" }, { id: "body", de: "koerper" }, { id: "nutrition", de: "ernaehrung" },
    { id: "kitchen", de: "kueche" }, { id: "sleep", de: "schlaf" }, { id: "substances", de: "konsum" },
    { id: "training", de: "training" }, { id: "journal", de: "journal" }
  ];
  var ALIAS = {};
  TABS.forEach(function (t) { ALIAS[t.id] = t.id; ALIAS[t.de] = t.id; });
  ALIAS["körper"] = "body"; ALIAS["ernährung"] = "nutrition"; ALIAS["küche"] = "kitchen";

  var PANTRY_ICON = { discard: "⛔", check: "🔍", soon: "⏳", ok: "✓" };
  var PANTRY_TONE = { discard: "critical", check: "serious", soon: "warning", ok: "good" };
  var TONE_ICON = { good: "✓", warning: "!", serious: "▲", critical: "✕", neutral: "–" };
  var LINE_ICON = "path://M0,4.5 L20,4.5 L20,7.5 L0,7.5 Z";
  var SLOTS = ["breakfast", "lunch", "dinner", "snack", "other"];
  var COSTS = ["groceries", "out", "tobacco", "cannabis", "alcohol", "coffee"];

  var state = { period: null, data: null, tab: "today", panels: {}, themeVer: 0, loading: false, review: null };
  var building = null; // panel whose cards are being built (charts register here)

  // ------------------------------------------------------------------------------------------
  // small helpers
  // ------------------------------------------------------------------------------------------

  function store(key, val) {
    try {
      if (val === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, val);
    } catch (e) { /* storage unavailable: per-session only */ }
    return null;
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function tpl(s, vars) {
    return String(s).replace(/\{(\w+)\}/g, function (_, k) { return vars[k] == null ? "" : vars[k]; });
  }

  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function num(v, nd) {
    if (!isNum(v)) return "–";
    nd = nd || 0;
    return new Intl.NumberFormat(T.locale, { minimumFractionDigits: nd, maximumFractionDigits: nd }).format(v);
  }

  function num1(v) { return num(v, isNum(v) && v % 1 ? 1 : 0); }

  function eur(v, cur) {
    if (!isNum(v)) return "–";
    try {
      return new Intl.NumberFormat(T.locale, { style: "currency", currency: cur || "EUR" }).format(v);
    } catch (e) { return num(v, 2) + " " + (cur || "EUR"); }
  }

  function signed(v, nd) {
    if (!isNum(v)) return "–";
    return (v > 0 ? "+" : v < 0 ? "−" : "±") + num(Math.abs(v), nd);
  }

  function mean(xs) {
    var v = xs.filter(isNum);
    return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null;
  }

  function sum(xs) { return xs.filter(isNum).reduce(function (a, b) { return a + b; }, 0); }

  function parseDay(s) {
    var p = s.split("-");
    return new Date(+p[0], +p[1] - 1, +(p[2] || 1));
  }

  function fmtDay(s, opts) { return new Intl.DateTimeFormat(T.locale, opts).format(parseDay(s)); }
  var DAY_SHORT = { day: "numeric", month: "short" };
  var DAY_AXIS = { day: "numeric", month: "numeric" };
  var DAY_LONG = { weekday: "short", day: "numeric", month: "short" };
  var MONTH = { month: "short", year: "numeric" };

  function daysBetween(a, b) { return Math.round((parseDay(b) - parseDay(a)) / 86400000); }

  function relDay(day, today) {
    var n = daysBetween(today, day);
    if (n === 0) return T.ago_today;
    if (n === 1) return T.tomorrow;
    return n > 0 ? tpl(T.in_days, { n: n }) : tpl(T.days_ago, { n: -n });
  }

  function hm(h) {
    if (!isNum(h)) return "–";
    var m = Math.round(h * 60);
    return Math.floor(m / 60) + " h " + (m % 60 < 10 ? "0" : "") + (m % 60) + " min";
  }

  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function clock(m) { m = ((Math.round(m) % 1440) + 1440) % 1440; return pad2(Math.floor(m / 60)) + ":" + pad2(m % 60); }
  function toMin(s) { if (!s) return null; var p = s.split(":"); return +p[0] * 60 + +p[1]; }

  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var day = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - day);
    var y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil(((t - y0) / 86400000 + 1) / 7);
  }

  // Group day rows into Monday-based weeks; add(week, row) accumulates.
  function weeksOf(days, init, add) {
    var out = [];
    days.forEach(function (d) {
      var dt = parseDay(d.day), wd = (dt.getDay() + 6) % 7;
      var key = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate() - wd).toDateString();
      var w = out.length && out[out.length - 1].key === key ? out[out.length - 1] : null;
      if (!w) { w = Object.assign({ key: key, kw: isoWeek(dt), from: d.day, to: d.day }, init()); out.push(w); }
      w.to = d.day;
      add(w, d);
    });
    return out;
  }
  function weekName(w) { return T.wk + w.kw; }
  function weekRange(w) { return weekName(w) + " · " + fmtDay(w.from, DAY_SHORT) + " – " + fmtDay(w.to, DAY_SHORT); }

  function trig(name) { return (T.triggers && T.triggers[name]) || I18N.en.triggers[name] || name; }
  function pretty(s) { s = String(s || "").replace(/^test_/, "").replace(/_/g, " "); return s.charAt(0).toUpperCase() + s.slice(1); }
  function mname(m) { return T.measure_names[m] || pretty(m); }
  function what(w) { return T.what[w] || T.cat[w] || w; }

  function pal() {
    var cs = getComputedStyle(document.documentElement);
    var g = function (n) { return cs.getPropertyValue(n).trim(); };
    var i, c = [], s = [];
    for (i = 1; i <= 8; i++) c.push(g("--c" + i));
    for (i = 1; i <= 7; i++) s.push(g("--s" + i));
    return {
      c: c, seq: s, other: g("--other"), text: g("--text"), text2: g("--text-2"), muted: g("--muted"),
      grid: g("--grid"), axis: g("--axis"), surface: g("--surface"), raised: g("--raised"), border: g("--border"),
      hover: g("--hover"), cell: g("--cell"), band: g("--band"), font: g("--font"),
      good: g("--good"), warning: g("--warning"), serious: g("--serious"), critical: g("--critical")
    };
  }

  // ------------------------------------------------------------------------------------------
  // chart building blocks (thin marks, recessive axes, text in text colours, one y-axis)
  // ------------------------------------------------------------------------------------------

  function grid(o) { return Object.assign({ left: 8, right: 14, top: 14, bottom: 2, containLabel: true }, o || {}); }

  function xCat(P, data, fmt) {
    return {
      type: "category", data: data, boundaryGap: true,
      axisLine: { lineStyle: { color: P.axis } }, axisTick: { show: false },
      axisLabel: { color: P.text2, fontSize: 11, hideOverlap: true, margin: 10, formatter: fmt },
      axisPointer: { label: { show: false } }
    };
  }
  function xDays(P, keys) { return xCat(P, keys, function (v) { return fmtDay(v, DAY_AXIS); }); }

  function yVal(P, o) {
    o = o || {};
    var y = Object.assign({ type: "value", splitNumber: 4, splitLine: { lineStyle: { color: P.grid } },
      axisLine: { show: false }, axisTick: { show: false } }, o);
    y.axisLabel = Object.assign({ color: P.text2, fontSize: 11, formatter: axisNum }, o.axisLabel || {});
    return y;
  }

  function axisNum(v) { return new Intl.NumberFormat(T.locale, { maximumFractionDigits: 2 }).format(v); }

  function yClock(P, o) {
    return yVal(P, Object.assign({ interval: 120, axisLabel: { formatter: function (v) { return clock(v); } } }, o || {}));
  }

  function legend(P, items, scroll) {
    return {
      type: scroll ? "scroll" : "plain", top: 0, left: 0, itemWidth: 12, itemHeight: 8, itemGap: 14,
      icon: "roundRect", textStyle: { color: P.text2, fontSize: 12 }, data: items,
      pageIconColor: P.text2, pageIconInactiveColor: P.axis, pageTextStyle: { color: P.text2 }
    };
  }

  function tooltip(P, trigger, pointer, formatter) {
    var t = {
      trigger: trigger, confine: true, transitionDuration: 0.15, formatter: formatter,
      backgroundColor: P.raised, borderColor: P.border, borderWidth: 1, padding: [9, 11],
      textStyle: { color: P.text, fontSize: 12, fontFamily: P.font },
      extraCssText: "border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.14);"
    };
    if (trigger === "axis") {
      t.axisPointer = pointer === "shadow" ? { type: "shadow", shadowStyle: { color: P.hover } }
        : { type: "line", lineStyle: { color: P.axis, width: 1 } };
    }
    return t;
  }

  // rows: [{color, label, value}] — everything is escaped here
  function tipHtml(title, rows, foot) {
    var h = '<div class="tt-title">' + esc(title) + "</div>";
    rows.forEach(function (r) {
      h += '<div class="tt-row">' + (r.color ? '<span class="tt-dot" style="background:' + esc(r.color) + '"></span>' : "") +
        '<span class="tt-label">' + esc(r.label) + '</span><span class="tt-val">' + esc(r.value) + "</span></div>";
    });
    if (foot) h += '<div class="tt-foot">' + esc(foot) + "</div>";
    return h;
  }

  function bar(name, data, color, o) {
    return Object.assign({
      name: name, type: "bar", data: data, barMaxWidth: 16, barCategoryGap: "28%",
      itemStyle: { color: color, borderRadius: [4, 4, 0, 0] }, emphasis: { itemStyle: { color: color } }
    }, o || {});
  }

  function line(name, data, color, o) {
    return Object.assign({
      name: name, type: "line", data: data, connectNulls: true, smooth: 0.2, symbol: "circle", symbolSize: 7, showAllSymbol: true,
      showSymbol: data.filter(function (v) { return v != null; }).length <= 40,
      lineStyle: { width: 2, color: color }, itemStyle: { color: color }, emphasis: { focus: "series", scale: 1.3 }
    }, o || {});
  }

  function refLine(P, value, label, pos) {
    return {
      silent: true, symbol: "none", animation: false,
      lineStyle: { color: P.text2, type: [4, 4], width: 1, opacity: 0.8 },
      label: { show: !!label, formatter: label, position: pos || "end", distance: 4, color: P.text2, fontSize: 11 },
      data: [{ yAxis: value }]
    };
  }

  // Direct label on the last real point (instead of endLabel, which animates from NaN on leading gaps).
  function lastLabel(data, label) {
    var out = data.slice();
    for (var i = out.length - 1; i >= 0; i--) {
      if (isNum(out[i])) {
        out[i] = { value: out[i], symbolSize: 7, label: Object.assign({ show: true, position: "right", distance: 6 }, label) };
        break;
      }
    }
    return out;
  }

  function pad(minPad) {
    return {
      scale: true,
      min: function (v) { return v.min - Math.max(minPad, (v.max - v.min) * 0.15); },
      max: function (v) { return v.max + Math.max(minPad, (v.max - v.min) * 0.15); },
      axisLabel: { showMinLabel: false, showMaxLabel: false }
    };
  }

  function has(rows, key) { return rows.some(function (r) { return isNum(r[key]); }); }

  function dayTable(days, cols) {
    var rows = [];
    days.forEach(function (d) {
      var vals = cols.map(function (c) { return c.get(d); });
      if (vals.some(function (v) { return v != null && v !== "–"; })) rows.push([fmtDay(d.day, DAY_LONG)].concat(vals));
    });
    return { head: [T.day].concat(cols.map(function (c) { return c.label; })),
      num: cols.map(function (c, i) { return c.num ? i + 1 : -1; }), rows: rows };
  }

  // Bars per week (one series). weeks: [{…, v}], fmt(v) -> string.
  function weekBars(P, weeks, color, name, fmt, o) {
    o = o || {};
    var s = bar(name, weeks.map(function (w) { return w.v; }), color, { barMaxWidth: 28 });
    if (o.ref != null) s.markLine = refLine(P, o.ref, o.refLabel);
    return {
      grid: grid({ top: 16, right: o.ref != null ? 52 : 14 }),
      tooltip: tooltip(P, "axis", "shadow", function (ps) {
        var w = weeks[ps[0].dataIndex];
        return tipHtml(weekRange(w), [{ color: color, label: name, value: fmt(w.v) }].concat(o.rows ? o.rows(w) : []));
      }),
      xAxis: xCat(P, weeks.map(weekName)), yAxis: yVal(P, o.y || {}), series: [s]
    };
  }

  function weekTable(weeks, label, fmt) {
    return { head: [T.week, label], num: [-1, 1], rows: weeks.map(function (w) { return [weekRange(w), fmt(w.v)]; }) };
  }

  // One 100 % horizontal bar from parts [{name, value, color, label}].
  function shareBar(P, parts, valFmt) {
    var total = sum(parts.map(function (p) { return p.value; })) || 1;
    return {
      grid: grid({ top: 4, bottom: 4, left: 0, right: 0, containLabel: false }),
      tooltip: tooltip(P, "item", null, function (p) {
        var x = parts[p.seriesIndex];
        return tipHtml(x.name, [{ color: x.color, label: "", value: valFmt(x) }]);
      }),
      xAxis: { type: "value", max: 100, show: false }, yAxis: { type: "category", data: [""], show: false },
      series: parts.map(function (x, i) {
        var last = i === parts.length - 1, first = i === 0;
        return { name: x.name, type: "bar", stack: "s", barWidth: 22, data: [x.value / total * 100],
          itemStyle: { color: x.color, borderColor: P.surface, borderWidth: 2,
            borderRadius: [first ? 6 : 0, last ? 6 : 0, last ? 6 : 0, first ? 6 : 0] } };
      })
    };
  }

  // ------------------------------------------------------------------------------------------
  // cards, sections, chips
  // ------------------------------------------------------------------------------------------

  var ICON_TABLE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 10h18M3 15h18M10 4v16"/></svg>';
  var ICON_CHART = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>';
  var ICON_EMPTY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3 12h4l2.5-6 5 12 2.5-6h4"/></svg>';

  function chip(tone, label, icon) {
    var c = el("span", "chip " + tone);
    c.appendChild(el("i", null, icon != null ? icon : TONE_ICON[tone] || ""));
    c.appendChild(document.createTextNode(label));
    return c;
  }

  function buildTable(t, cls) {
    var table = el("table", cls || "data-table"), thead = el("thead"), tr = el("tr");
    t.head.forEach(function (h, i) { tr.appendChild(el("th", t.num.indexOf(i) >= 0 ? "num" : null, h)); });
    thead.appendChild(tr);
    table.appendChild(thead);
    var tb = el("tbody");
    t.rows.forEach(function (r) {
      var row = el("tr");
      r.forEach(function (v, i) {
        var td = el("td", t.num.indexOf(i) >= 0 ? "num" : null);
        if (v instanceof Node) td.appendChild(v); else td.textContent = v == null ? "–" : String(v);
        row.appendChild(td);
      });
      tb.appendChild(row);
    });
    table.appendChild(tb);
    return table;
  }

  function emptyBox(text, hint) {
    var e = el("div", "empty");
    e.innerHTML = ICON_EMPTY;
    e.appendChild(el("span", null, text || T.empty));
    if (hint) e.appendChild(el("span", "empty-hint", hint));
    return e;
  }

  // spec: {title, sub, empty, emptyText, hint, option(P, w), table(), note, cls, custom(body), after(body), badge}
  function addCard(gridEl, spec, cls) {
    var card = el("article", "card" + (cls ? " " + cls : "") + (spec.cls ? " " + spec.cls : ""));
    var head = el("div", "card-head"), titles = el("div", "card-titles");
    var h3 = el("h3", null, spec.title);
    h3.id = "c" + Math.random().toString(36).slice(2, 9);
    titles.appendChild(h3);
    if (spec.sub) titles.appendChild(el("p", null, spec.sub));
    head.appendChild(titles);
    if (spec.badge) head.appendChild(spec.badge);
    card.appendChild(head);
    card.setAttribute("aria-labelledby", h3.id);
    gridEl.appendChild(card);

    if (spec.empty) {
      card.appendChild(emptyBox(spec.emptyText, spec.hint));
      return card;
    }
    if (spec.custom) {
      spec.custom(card);
      if (spec.note) card.appendChild(el("p", "note", spec.note));
      return card;
    }
    var chartEl = el("div", "chart" + (spec.chartCls ? " " + spec.chartCls : ""));
    chartEl.setAttribute("role", "img");
    chartEl.setAttribute("aria-label", spec.title + (spec.sub ? " – " + spec.sub : ""));
    card.appendChild(chartEl);
    var wrap = el("div", "table-wrap");
    wrap.hidden = true;
    card.appendChild(wrap);
    if (spec.after) spec.after(card);
    if (spec.note) card.appendChild(el("p", "note", spec.note));

    if (spec.table) {
      var btn = el("button", "toggle");
      btn.type = "button";
      btn.setAttribute("aria-pressed", "false");
      var setBtn = function (on) {
        btn.innerHTML = on ? ICON_CHART : ICON_TABLE;
        btn.appendChild(document.createTextNode(on ? T.chart : T.table));
      };
      setBtn(false);
      head.appendChild(btn);
      btn.addEventListener("click", function () {
        var on = btn.getAttribute("aria-pressed") !== "true";
        btn.setAttribute("aria-pressed", String(on));
        if (on && !wrap.firstChild) wrap.appendChild(buildTable(spec.table()));
        wrap.hidden = !on;
        chartEl.hidden = on;
        setBtn(on);
        if (!on && entry.inst) entry.inst.resize();
      });
    }
    var entry = { el: chartEl, spec: spec, inst: null, wide: null };
    building.charts.push(entry);
    return card;
  }

  function section(root, title, sub, gridCls) {
    var s = el("section", "section"), h = el("div", "section-head");
    h.appendChild(el("h2", null, title));
    if (sub) h.appendChild(el("p", null, sub));
    s.appendChild(h);
    var g = el("div", "grid" + (gridCls ? " " + gridCls : ""));
    s.appendChild(g);
    root.appendChild(s);
    return g;
  }

  function renderChart(entry, P) {
    if (entry.el.hidden) return;
    var w = entry.el.clientWidth || 600;
    entry.wide = w >= 520;
    var opt = entry.spec.option(P, w);
    opt.textStyle = { fontFamily: P.font, color: P.text2 };
    opt.animationDuration = 450;
    opt.animationDurationUpdate = 250;
    if (!entry.inst) entry.inst = echarts.init(entry.el, null, { renderer: "svg" });
    entry.inst.setOption(opt, { notMerge: true });
  }

  function renderPanelCharts(panel) {
    var P = pal();
    panel.charts.forEach(function (c) { renderChart(c, P); });
    panel.themeVer = state.themeVer;
  }

  function resizePanelCharts(panel) {
    var P = null;
    panel.charts.forEach(function (c) {
      if (!c.inst || c.el.hidden) return;
      var wide = (c.el.clientWidth || 600) >= 520;
      if (wide !== c.wide) { P = P || pal(); renderChart(c, P); } else c.inst.resize();
    });
  }

  // ------------------------------------------------------------------------------------------
  // KPI tiles
  // ------------------------------------------------------------------------------------------

  function spark(values, colorVar) {
    var NS = "http://www.w3.org/2000/svg", W = 120, H = 28;
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    var pts = [];
    values.forEach(function (v, i) { if (isNum(v)) pts.push([i, v]); });
    if (pts.length < 2) return svg;
    var lo = Math.min.apply(null, pts.map(function (p) { return p[1]; }));
    var hi = Math.max.apply(null, pts.map(function (p) { return p[1]; }));
    var n = Math.max(values.length - 1, 1), span = hi - lo || 1;
    var xy = function (p) { return [(p[0] / n) * W, H - 3 - ((p[1] - lo) / span) * (H - 6)]; };
    var d = pts.map(function (p, i) { var q = xy(p); return (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1); }).join(" ");
    var path = document.createElementNS(NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("vector-effect", "non-scaling-stroke");
    path.style.stroke = "var(" + colorVar + ")";
    svg.appendChild(path);
    return svg;
  }

  function kpi(root, o) {
    var t = el("div", "kpi");
    var lab = el("div", "kpi-label");
    if (o.color) {
      var dot = el("span", "kpi-dot");
      dot.style.background = "var(" + o.color + ")";
      lab.appendChild(dot);
    }
    lab.appendChild(document.createTextNode(o.label));
    t.appendChild(lab);
    var v = el("div", "kpi-value", o.value);
    if (o.unit && o.value !== "–") v.appendChild(el("small", null, o.unit));
    t.appendChild(v);
    t.appendChild(el("div", "kpi-sub", o.sub || ""));
    if (o.spark) { var s = el("div", "kpi-spark"); s.appendChild(spark(o.spark, o.color)); t.appendChild(s); }
    if (o.pips) {
      var p = el("div", "kpi-pips");
      p.setAttribute("aria-hidden", "true");
      for (var i = 0; i < o.pips[1]; i++) p.appendChild(el("span", i < o.pips[0] ? "on" : null));
      t.appendChild(p);
    }
    root.appendChild(t);
    return t;
  }

  function renderKpis(root, D) {
    var days = D.days, TD = D.tabs.today, NT = D.tabs.nutrition.targets || {};
    var last = function (k) { for (var i = days.length - 1; i >= 0; i--) if (isNum(days[i][k])) return i; return -1; };
    var col = function (k) { return days.map(function (d) { return d[k]; }); };
    var wi = last("weight_7d"), wv = wi >= 0 ? days[wi].weight_7d : null;
    var wPrev = wi >= 7 ? days[wi - 7].weight_7d : null;
    kpi(root, { label: T.kpi_weight, color: "--c1", value: num(wv, 1), unit: "kg",
      sub: isNum(wv) && isNum(wPrev) ? signed(wv - wPrev, 1) + " kg " + T.kpi_weight_sub_delta : T.kpi_weight_sub,
      spark: col("weight_7d") });
    var pm = mean(col("protein_g")), pt = NT.protein_g;
    kpi(root, { label: T.kpi_protein, color: "--c3", value: num(pm), unit: "g",
      sub: pt && isNum(pm) ? T.kpi_protein_target + " " + num(pt[0]) + (pt[1] ? "–" + num(pt[1]) : "") + " g · " + Math.round(pm / pt[0] * 100) + " %" : T.kpi_protein_sub,
      spark: col("protein_g") });
    var sm = mean(col("sleep_h")), sq = mean(col("sleep_quality"));
    kpi(root, { label: T.kpi_sleep, color: "--c7", value: isNum(sm) ? num(sm, 1) : "–", unit: "h",
      sub: isNum(sq) ? T.kpi_sleep_q + " " + num(sq, 1) + " / 5" : "", spark: col("sleep_h") });
    var kinds = Object.keys(D.tabs.substances.substance_kinds || {});
    var useLabel = kinds.length === 1 && T["kpi_" + kinds[0]] ? T["kpi_" + kinds[0]] : T.kpi_use;
    var logged = days.filter(function (d) { return d.logged; });
    var subTotal = sum(days.map(function (d) { return d.substance_n; }));
    var tobTotal = sum(days.map(function (d) { return d.tobacco_n; }));
    var rate = logged.length ? subTotal / logged.length : null;
    var sub = T.kpi_tobacco + " " + (logged.length ? num(tobTotal / logged.length, 1) : "–");
    var pv = D.previous;
    if (isNum(rate) && pv && pv.days_logged > 0) sub += " · " + signed(rate - pv.substance_n / pv.days_logged, 1) + " " + T.kpi_prev;
    kpi(root, { label: useLabel, color: "--c2", value: isNum(rate) ? num(rate, 1) : "–", sub: logged.length ? sub : "",
      spark: days.map(function (d) { return d.logged ? d.substance_n : null; }) });
    var plan = TD.training_plan || 4, wk = TD.week || { training_n: 0, training_min: 0 };
    kpi(root, { label: T.kpi_train, color: "--c1", value: wk.training_n + " / " + plan,
      sub: tpl(T.kpi_train_sub, { n: plan }) + (wk.training_min ? " · " + num(wk.training_min) + " min" : ""),
      pips: [Math.min(wk.training_n, Math.max(plan, wk.training_n)), Math.max(plan, wk.training_n)] });
  }

  // ------------------------------------------------------------------------------------------
  // tab: today
  // ------------------------------------------------------------------------------------------

  function listRow(list, icon, label, value) {
    var li = el("li", "row");
    li.appendChild(icon);
    li.appendChild(el("span", "row-label", label));
    if (value != null) li.appendChild(el("span", "row-value", value));
    list.appendChild(li);
    return li;
  }

  function tabToday(root, D) {
    var TD = D.tabs.today;
    var g = section(root, null, null, "grid-top");
    // phase banner
    addCard(g, { title: TD.phase ? T.phase : T.no_phase, cls: "phase-card", custom: function (card) {
      if (!TD.phase) { card.appendChild(el("p", "muted-text", T.no_phase_hint)); return; }
      var p = TD.phase, wrap = el("div", "phase");
      var left = el("div", "phase-main");
      left.appendChild(el("div", "phase-name", p.name));
      var meta = el("div", "phase-meta", p.of ? tpl(T.phase_day, { x: p.day, y: p.of }) : tpl(T.phase_day_open, { x: p.day }));
      left.appendChild(meta);
      if (p.of) {
        var prog = el("div", "progress");
        prog.setAttribute("role", "progressbar");
        prog.setAttribute("aria-valuemin", "0");
        prog.setAttribute("aria-valuemax", String(p.of));
        prog.setAttribute("aria-valuenow", String(Math.min(p.day, p.of)));
        var fill = el("span");
        fill.style.width = Math.min(100, p.day / p.of * 100) + "%";
        prog.appendChild(fill);
        left.appendChild(prog);
      }
      if (p.focus) left.appendChild(el("p", "phase-focus", p.focus));
      wrap.appendChild(left);
      var dec = el("div", "phase-side"), nd = TD.next_decision;
      dec.appendChild(el("div", "eyebrow", T.next_decision));
      if (nd) {
        dec.appendChild(el("div", "decision-title", nd.title));
        if (nd.date) {
          var when = el("div", "decision-when");
          when.appendChild(document.createTextNode(fmtDay(nd.date, DAY_LONG) + " · "));
          when.appendChild(nd.days_left < 0 ? chip("warning", T.overdue) : el("b", null, relDay(nd.date, D.today)));
          dec.appendChild(when);
        }
        if (nd.note) dec.appendChild(el("div", "decision-note", nd.note));
      } else dec.appendChild(el("div", "muted-text", T.no_decision));
      wrap.appendChild(dec);
      card.appendChild(wrap);
    } }, "wide");
    // focus of the week
    addCard(g, { title: T.focus, cls: "focus-card full", custom: function (card) {
      if (!TD.focus) { card.appendChild(el("p", "focus-text muted-text", T.no_focus)); card.appendChild(el("p", "note", T.no_focus_hint)); return; }
      var p = el("p", "focus-text");
      p.innerHTML = window.BosMarkdown.inline(TD.focus.text);
      card.appendChild(p);
      var a = el("a", "link", tpl(T.focus_from, { file: TD.focus.file }));
      a.href = "#" + slugFor("journal");
      a.addEventListener("click", function () { state.review = TD.focus.file; });
      card.appendChild(a);
    } });

    g = section(root, null, null);
    // checklist
    var cl = TD.checklist || [];
    addCard(g, { title: T.checklist, sub: tpl(T.checklist_sub, { done: cl.filter(function (c) { return c.done; }).length, n: cl.length }),
      custom: function (card) {
        var ul = el("ul", "rows");
        cl.forEach(function (c) {
          var label = T.ck[c.type] || pretty(c.key), val;
          if (c.type === "weight" && isNum(c.value)) val = num(c.value, 1) + " kg";
          else if (c.type === "sleep" && isNum(c.value)) val = hm(c.value);
          else if (c.min > 1) val = tpl(T.ck_meals, { n: c.n, m: c.min });
          else val = null;
          listRow(ul, chip(c.done ? "good" : "neutral", c.done ? T.done : T.open), label, val);
        });
        if (TD.substances) {
          var s = TD.substances;
          var li = listRow(ul, el("span", "row-dot"), T.ck_subs, s.n ? tpl(T.ck_subs_val, { n: s.n, t: s.last || "–" }) : T.ck_subs_none);
          li.classList.add("row-info");
        }
        card.appendChild(ul);
      } });
    // due today
    var due = TD.due || {};
    addCard(g, { title: T.due_today, custom: function (card) {
      var ul = el("ul", "rows"), any = false;
      (due.training || []).forEach(function (t) {
        any = true;
        listRow(ul, chip(t.done ? "good" : "warning", t.done ? T.done : T.due), tpl(T.due_training, { what: what(t.what) }),
          t.done && t.done_day !== D.today ? fmtDay(t.done_day, DAY_LONG) : null);
      });
      (due.measurements || []).forEach(function (m) {
        any = true;
        var tone = m.status === "done" ? "good" : m.status === "due" ? "warning" : "neutral";
        var lab = m.status === "done" ? T.done : m.status === "due" ? T.due : T.open;
        listRow(ul, chip(tone, lab), mname(m.metric), m.of ? tpl(T.this_week, { n: m.count, m: m.of }) : null);
      });
      if (due.review) {
        any = true;
        listRow(ul, chip(due.review.done ? "good" : "warning", due.review.done ? T.done : T.due), T.due_review, due.review.file);
      }
      if (!any) card.appendChild(el("p", "muted-text", T.nothing_due));
      card.appendChild(ul);
      if (due.training_next) {
        card.appendChild(el("p", "note", tpl(T.next_training, { day: fmtDay(due.training_next.day, { weekday: "long" }), what: what(due.training_next.what) })));
      }
    } });
    // pantry alerts
    var pa = TD.pantry_alerts || { counts: {}, top: [] };
    addCard(g, { title: T.pantry_alerts, custom: function (card) {
      var counts = el("div", "chip-row");
      ["discard", "check", "soon"].forEach(function (s) {
        if (pa.counts[s]) counts.appendChild(chip(PANTRY_TONE[s], pa.counts[s] + " × " + T["status_" + s], PANTRY_ICON[s]));
      });
      if (!counts.firstChild) card.appendChild(el("p", "muted-text", T.pantry_alerts_none));
      else card.appendChild(counts);
      var ul = el("ul", "rows");
      pa.top.forEach(function (it) {
        listRow(ul, chip(PANTRY_TONE[it.status], T["status_" + it.status], PANTRY_ICON[it.status]), it.name, expiryText(it.days_left));
      });
      card.appendChild(ul);
      var a = el("a", "link", T.to_kitchen + " →");
      a.href = "#" + slugFor("kitchen");
      card.appendChild(a);
    } });

    // spending this month
    var sp = TD.spend_month;
    g = section(root, null, null);
    var cats = sp ? sp.categories.filter(function (c) { return c.any; }) : [];
    var known = cats.filter(function (c) { return c.eur > 0; });
    addCard(g, {
      title: T.spend, sub: sp ? tpl(T.spend_sub, { from: fmtDay(sp.from, DAY_SHORT), to: fmtDay(sp.to, DAY_SHORT) }) : null,
      cls: "spend-card", empty: !known.length, emptyText: T.spend_none, hint: T.spend_hint,
      badge: known.length ? el("div", "big-num", (sp.estimated ? "≈ " : "") + eur(sp.total, sp.currency)) : null,
      option: function (P) {
        return shareBar(P, known.map(function (c) {
          return { name: T.cost[c.key], value: c.eur, color: P.c[COSTS.indexOf(c.key)], c: c };
        }), function (x) { return (x.c.est ? "≈ " : "") + eur(x.value, sp.currency) + " · " + Math.round(x.value / sp.total * 100) + " %"; });
      },
      chartCls: "chart-bar",
      after: function (card) {
        var ul = el("ul", "legend-list");
        cats.forEach(function (c) {
          var li = el("li");
          var dot = el("span", "dot");
          dot.style.background = "var(--c" + (COSTS.indexOf(c.key) + 1) + ")";
          li.appendChild(dot);
          li.appendChild(el("span", "ll-label", T.cost[c.key]));
          li.appendChild(el("span", "ll-value", c.eur > 0 ? (c.est ? "≈ " : "") + eur(c.eur, sp.currency) : "–"));
          ul.appendChild(li);
        });
        card.appendChild(ul);
        var foot = el("div", "card-foot");
        if (sp.unknown) foot.appendChild(el("span", "note", tpl(T.spend_unknown, { n: sp.unknown })));
        if (sp.estimated) foot.appendChild(el("span", "note", T.est));
        var a = el("a", "link", T.to_details + " →");
        a.href = "#" + slugFor(cats.some(function (c) { return ["tobacco", "cannabis", "alcohol"].indexOf(c.key) >= 0 && c.eur > 0; }) ? "substances" : "kitchen");
        foot.appendChild(a);
        card.appendChild(foot);
      },
      table: function () {
        return { head: ["", "€", "≈"], num: [1], rows: cats.map(function (c) { return [T.cost[c.key], eur(c.eur, sp.currency), c.est ? "≈" : ""]; }) };
      }
    }, "full");

    var ks = section(root, T.kpis, T.kpis_sub, "kpis");
    renderKpis(ks, D);
  }

  function expiryText(dl) {
    return dl == null ? T.no_date : dl === 0 ? T.today : dl > 0 ? tpl(T.days_left, { n: dl }) : tpl(T.days_past, { n: -dl });
  }

  // ------------------------------------------------------------------------------------------
  // tab: body
  // ------------------------------------------------------------------------------------------

  function measureCard(g, D, key, title, unit, nd, emptyText) {
    var s = key.points || [], keys = D.days.map(function (d) { return d.day; });
    var at = {};
    s.forEach(function (p) { at[p.day] = p; });
    var latest = key.latest, prev = key.previous;
    var sub = unit;
    if (latest) sub += " · " + T.latest + " " + num(latest.value, nd) + (prev ? " (" + signed(latest.value - prev.value, nd) + ")" : "");
    addCard(g, {
      title: title, sub: sub, empty: !s.length,
      emptyText: latest ? tpl(T.no_period_value, { v: num(latest.value, nd) + " " + unit, d: fmtDay(latest.day, DAY_SHORT) }) : emptyText || T.empty,
      option: function (P) {
        return {
          grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var k = keys[ps[0].dataIndex], p = at[k];
            return tipHtml(fmtDay(k, DAY_LONG), [{ color: P.c[0], label: title, value: p ? num(p.value, nd) + " " + unit : "–" }]);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(nd ? 0.5 : 2)),
          series: [line(title, keys.map(function (k) { return at[k] ? at[k].value : null; }), P.c[0], { showSymbol: true, smooth: false })]
        };
      },
      table: function () { return { head: [T.day, unit], num: [-1, 1], rows: s.map(function (p) { return [fmtDay(p.day, DAY_LONG), num(p.value, nd)]; }) }; }
    });
  }

  function tabBody(root, D) {
    var B = D.tabs.body, days = D.days, keys = days.map(function (d) { return d.day; });
    var col = function (k) { return days.map(function (d) { return isNum(d[k]) ? d[k] : null; }); };
    var cor = B.corridor, corAt = {};
    if (cor) cor.days.forEach(function (c) { corAt[c.day] = c; });
    var g = section(root, T.sec_weight, null);
    addCard(g, {
      title: T.weight, sub: T.weight_sub, empty: !has(days, "weight_kg"), cls: "tall",
      note: cor ? tpl(T.corridor_note, { lo: signed(cor.rate[0], 1), hi: signed(cor.rate[1], 1), kg: num(cor.anchor_kg, 1), day: fmtDay(cor.anchor_day, DAY_SHORT) }) : T.corridor_hint,
      option: function (P) {
        var items = [{ name: T.daily, icon: "circle" }, { name: T.avg7, icon: LINE_ICON }];
        var series = [
          { name: T.daily, type: "scatter", data: col("weight_kg"), symbolSize: 8, z: 3,
            itemStyle: { color: P.c[0], opacity: 0.45, borderColor: P.surface, borderWidth: 1.5 } },
          line(T.avg7, lastLabel(col("weight_7d"), { color: P.text, fontWeight: 600, fontSize: 12,
            formatter: function (p) { return num(p.value, 1) + " kg"; } }), P.c[0], { showSymbol: true, symbolSize: 0, z: 4 })
        ];
        if (cor) {
          items.push({ name: T.corridor, icon: "roundRect" });
          var lo = keys.map(function (k) { return corAt[k] ? corAt[k].lo : null; });
          var span = keys.map(function (k) { return corAt[k] ? Math.round((corAt[k].hi - corAt[k].lo) * 100) / 100 : null; });
          series.unshift(
            { name: "_lo", type: "line", data: lo, stack: "cor", symbol: "none", lineStyle: { opacity: 0 }, silent: true,
              tooltip: { show: false }, z: 1 },
            { name: T.corridor, type: "line", data: span, stack: "cor", symbol: "none", lineStyle: { opacity: 0 }, silent: true,
              areaStyle: { color: P.c[2], opacity: 0.14 }, itemStyle: { color: P.c[2] }, z: 1 });
        }
        return {
          grid: grid({ top: 36, right: 58 }), legend: legend(P, items),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var d = days[ps[0].dataIndex], c = corAt[d.day], r = [
              { color: P.c[0], label: T.daily, value: isNum(d.weight_kg) ? num(d.weight_kg, 1) + " kg" : "–" },
              { color: P.c[0], label: T.avg7, value: isNum(d.weight_7d) ? num(d.weight_7d, 1) + " kg" : "–" }];
            if (c) r.push({ color: P.c[2], label: T.corridor, value: num(c.hi, 1) + "–" + num(c.lo, 1) + " kg" });
            return tipHtml(fmtDay(d.day, DAY_LONG), r);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(1)), series: series
        };
      },
      table: function () {
        return dayTable(days, [
          { label: T.daily + " (kg)", num: true, get: function (d) { return isNum(d.weight_kg) ? num(d.weight_kg, 1) : null; } },
          { label: T.avg7 + " (kg)", num: true, get: function (d) { return isNum(d.weight_kg) ? num(d.weight_7d, 2) : null; } },
          { label: T.corridor + " (kg)", num: true, get: function (d) { var c = corAt[d.day]; return c && isNum(d.weight_kg) ? num(c.hi, 1) + "–" + num(c.lo, 1) : null; } }]);
      }
    }, "full");

    var circ = B.circumferences || {};
    var withData = ["waist_cm", "arm_cm", "chest_cm", "thigh_cm"].filter(function (m) { return circ[m] && circ[m].latest; });
    g = section(root, T.sec_circ, T.sec_circ_sub, "grid-4");
    if (!withData.length) addCard(g, { title: T.sec_circ, empty: true }, "full");
    withData.forEach(function (m) { measureCard(g, D, circ[m], mname(m), "cm", 1); });

    g = section(root, T.sec_heart, null);
    var bp = B.bp || { points: [] }, bpAt = {};
    bp.points.forEach(function (p) { bpAt[p.day] = p; });
    var lt = bp.latest, CAT_TONE = { optimal: "good", normal: "good", high_normal: "warning", hypertension: "serious" };
    addCard(g, {
      title: T.bp, sub: T.bp_sub + (lt ? " · " + T.latest + " " + lt.sys + "/" + lt.dia + " (" + fmtDay(lt.day, DAY_SHORT) + ")" : ""),
      empty: !bp.points.length, emptyText: lt ? tpl(T.no_period_value, { v: lt.sys + "/" + lt.dia, d: fmtDay(lt.day, DAY_SHORT) }) : null,
      badge: lt ? chip(CAT_TONE[lt.category], T.bp_cat[lt.category]) : null, note: T.bp_note,
      option: function (P) {
        var zone = function (a, b, c, o) { return [{ yAxis: a, itemStyle: { color: c, opacity: o } }, { yAxis: b }]; };
        var sys = line(T.sys, keys.map(function (k) { return bpAt[k] ? bpAt[k].sys : null; }), P.c[0], { showSymbol: true, smooth: false });
        sys.markArea = { silent: true, animation: false, label: { show: false },
          data: [zone(130, 140, P.warning, 0.10), zone(140, 220, P.serious, 0.10)] };
        var dia = line(T.dia, keys.map(function (k) { return bpAt[k] ? bpAt[k].dia : null; }), P.c[1], { showSymbol: true, smooth: false });
        dia.markLine = { silent: true, symbol: "none", animation: false,
          lineStyle: { color: P.text2, type: [3, 4], width: 1, opacity: 0.6 },
          label: { show: true, position: "insideEndTop", color: P.text2, fontSize: 10, formatter: function (p) { return p.value; } },
          data: [{ yAxis: 85, label: { position: "insideEndBottom" } }, { yAxis: 90 }] };
        return {
          grid: grid({ top: 36, right: 18 }),
          legend: legend(P, [{ name: T.sys, icon: LINE_ICON }, { name: T.dia, icon: LINE_ICON }]),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var k = keys[ps[0].dataIndex], p = bpAt[k];
            if (!p) return tipHtml(fmtDay(k, DAY_LONG), [{ label: T.bp, value: "–" }]);
            var r = [{ color: P.c[0], label: T.sys, value: p.sys + " mmHg" }, { color: P.c[1], label: T.dia, value: p.dia + " mmHg" }];
            if (isNum(p.pulse)) r.push({ label: T.pulse, value: p.pulse + " /min" });
            return tipHtml(fmtDay(k, DAY_LONG), r, TONE_ICON[CAT_TONE[p.category]] + " " + T.bp_cat[p.category]);
          }),
          xAxis: xDays(P, keys),
          yAxis: yVal(P, { min: function (v) { return Math.min(60, Math.floor(v.min / 10) * 10); },
            max: function (v) { return Math.max(150, Math.ceil(v.max / 10) * 10 + 10); }, interval: 20 }),
          series: [sys, dia]
        };
      },
      after: function (card) { card.appendChild(el("p", "note legend-text", T.bp_legend)); },
      table: function () {
        return { head: [T.day, T.sys, T.dia, T.pulse, T.status], num: [1, 2, 3],
          rows: bp.points.map(function (p) { return [fmtDay(p.day, DAY_LONG), String(p.sys), String(p.dia), isNum(p.pulse) ? String(p.pulse) : "–", chip(CAT_TONE[p.category], T.bp_cat[p.category])]; }) };
      }
    }, "wide");
    var vit = B.vitals || {};
    ["resting_hr", "hrv_ms", "vo2max"].forEach(function (m) { if (vit[m]) measureCard(g, D, vit[m], T.vit[m], T.vit_unit[m], m === "vo2max" ? 1 : 0); });
    if (!vit.resting_hr) addCard(g, { title: T.vit.resting_hr, empty: true });

    g = section(root, null, null);
    var labs = B.labs || [];
    addCard(g, { title: T.labs, sub: T.labs_sub, empty: !labs.length, custom: function (card) {
      var wrap = el("div", "table-wrap static");
      wrap.appendChild(buildTable({
        head: [T.test, T.value, T.ref, T.status, T.previous, T.date], num: [1, 2, 4],
        rows: labs.map(function (l) {
          var ref = isNum(l.ref_low) && isNum(l.ref_high) ? num1(l.ref_low) + "–" + num1(l.ref_high)
            : isNum(l.ref_low) ? "≥ " + num1(l.ref_low) : isNum(l.ref_high) ? "≤ " + num1(l.ref_high) : "–";
          var st = l.flag === "in" ? chip("good", T.lab_in) : l.flag === "low" ? chip("warning", T.lab_low, "↓")
            : l.flag === "high" ? chip("warning", T.lab_high, "↑") : "–";
          var v = (isNum(l.value) ? num1(l.value) : String(l.value)) + (l.unit ? " " + l.unit : "");
          return [pretty(l.test), v, ref, st, l.previous != null ? (isNum(l.previous) ? num1(l.previous) : String(l.previous)) + (l.previous_date ? " (" + fmtDay(l.previous_date, MONTH) + ")" : "") : "–", fmtDay(l.date, DAY_SHORT)];
        })
      }));
      card.appendChild(wrap);
    } }, "full");
  }

  // ------------------------------------------------------------------------------------------
  // tab: nutrition
  // ------------------------------------------------------------------------------------------

  function tabNutrition(root, D) {
    var N = D.tabs.nutrition, days = D.days, keys = days.map(function (d) { return d.day; });
    var col = function (k) { return days.map(function (d) { return isNum(d[k]) ? d[k] : null; }); };
    function dayTip(P, rowsFor) {
      return tooltip(P, "axis", "shadow", function (ps) { var i = ps[0].dataIndex; return tipHtml(fmtDay(days[i].day, DAY_LONG), rowsFor(days[i], i)); });
    }
    function bandBar(P, key, color, name, unit, t) {
      var vals = col(key), mx = Math.max.apply(null, vals.filter(isNum).concat([0]));
      var top = t ? Math.ceil(Math.max(mx, t[1] || t[0] * 1.15) * 1.08 / 20) * 20 : null;
      var s = bar(name, vals, color);
      if (t) {
        s.markArea = { silent: true, animation: false, itemStyle: { color: P.band }, data: [[{ yAxis: t[0] }, { yAxis: t[1] || top }]] };
        s.markLine = refLine(P, t[0], T.target + " " + num(t[0]) + (t[1] ? "–" + num(t[1]) : "") + " " + unit, "insideStartTop");
      }
      return {
        grid: grid({ top: 16 }),
        tooltip: dayTip(P, function (d) {
          var r = [{ color: color, label: name, value: isNum(d[key]) ? num(d[key]) + " " + unit : "–" }];
          if (t && isNum(d[key])) r.push({ label: T.target, value: Math.round(d[key] / t[0] * 100) + " %" });
          return r;
        }),
        xAxis: xDays(P, keys), yAxis: yVal(P, top ? { max: top } : {}), series: [s]
      };
    }
    var tg = N.targets || {}, pb = tg.protein_basis;
    var g = section(root, T.sec_intake, null, "grid-2");
    addCard(g, {
      title: T.protein, sub: T.protein_sub + (pb ? " · " + tpl(T.protein_basis, { lo: num(pb.g_per_kg[0], 1), hi: num(pb.g_per_kg[1], 1), kg: num(pb.weight_kg, 1) }) : ""),
      empty: !has(days, "protein_g"), option: function (P) { return bandBar(P, "protein_g", P.c[2], T.protein, "g", tg.protein_g); },
      table: function () { return dayTable(days, [{ label: T.protein + " (g)", num: true, get: function (d) { return isNum(d.protein_g) ? num(d.protein_g) : null; } }]); }
    });
    addCard(g, {
      title: T.kcal, sub: T.kcal_sub, empty: !has(days, "kcal"), option: function (P) { return bandBar(P, "kcal", P.c[1], T.kcal, "kcal", tg.kcal); },
      table: function () { return dayTable(days, [{ label: "kcal", num: true, get: function (d) { return isNum(d.kcal) ? num(d.kcal) : null; } }]); }
    });

    var slots = N.slots || [];
    var usedSlots = SLOTS.filter(function (s) { return slots.some(function (r) { return isNum(r[s]); }); });
    var slotMeans = usedSlots.map(function (s) { return T.slot[s] + " " + num(mean(slots.map(function (r) { return r[s]; }))) + " g"; });
    addCard(g, {
      title: T.slots, sub: T.slots_sub, empty: !usedSlots.length, note: usedSlots.length ? "Ø " + slotMeans.join(" · ") : null,
      option: function (P) {
        var color = function (s) { return s === "other" ? P.other : P.c[SLOTS.indexOf(s)]; };
        var topIdx = slots.map(function (r) { var t = -1; usedSlots.forEach(function (s, i) { if (r[s] > 0) t = i; }); return t; });
        return {
          grid: grid({ top: 38 }), legend: legend(P, usedSlots.map(function (s) { return T.slot[s]; })),
          tooltip: dayTip(P, function (d, i) {
            var r = slots[i], rows = usedSlots.filter(function (s) { return isNum(r[s]); }).map(function (s) { return { color: color(s), label: T.slot[s], value: num(r[s]) + " g" }; });
            rows.push({ label: T.total, value: isNum(d.protein_g) ? num(d.protein_g) + " g" : "–" });
            return rows;
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P),
          series: usedSlots.map(function (s, si) {
            return { name: T.slot[s], type: "bar", stack: "slot", barMaxWidth: 16, barCategoryGap: "28%",
              itemStyle: { color: color(s), borderColor: P.surface, borderWidth: 1 }, emphasis: { focus: "series" },
              data: slots.map(function (r, i) { var v = isNum(r[s]) ? r[s] : null; return topIdx[i] === si ? { value: v, itemStyle: { borderRadius: [4, 4, 0, 0] } } : v; }) };
          })
        };
      },
      table: function () {
        return dayTable(days.map(function (d, i) { return Object.assign({}, d, { _s: slots[i] }); }),
          usedSlots.map(function (s) { return { label: T.slot[s] + " (g)", num: true, get: function (d) { return isNum(d._s[s]) ? num(d._s[s]) : null; } }; }));
      }
    });

    var M = N.macros || {}, MK = ["protein_g", "carbs_g", "fat_g"];
    var pct = M.kcal_pct || {}, gpd = M.g_per_day || {};
    addCard(g, {
      title: T.macros, sub: T.macros_sub, empty: !M.meals, chartCls: "chart-bar",
      option: function (P) {
        return shareBar(P, MK.map(function (k, i) { return { name: T.macro[k], value: pct[k] || 0, color: P.c[i], k: k }; }),
          function (x) { return num(pct[x.k], 0) + " % · " + num(gpd[x.k]) + " g " + T.per_day; });
      },
      after: function (card) {
        var ul = el("ul", "legend-list");
        MK.forEach(function (k, i) {
          var li = el("li"), dot = el("span", "dot");
          dot.style.background = "var(--c" + (i + 1) + ")";
          li.appendChild(dot);
          li.appendChild(el("span", "ll-label", T.macro[k]));
          li.appendChild(el("span", "ll-value", num(pct[k], 0) + " % · " + num(gpd[k]) + " g"));
          ul.appendChild(li);
        });
        card.appendChild(ul);
      },
      table: function () { return { head: ["", "g " + T.per_day, T.share], num: [1, 2], rows: MK.map(function (k) { return [T.macro[k], num(gpd[k]), num(pct[k], 0) + " %"]; }) }; }
    });

    g = section(root, null, null);
    var mt = N.meal_times || [];
    addCard(g, {
      title: T.timing, sub: T.timing_sub, empty: !mt.length, cls: "tall",
      option: function (P) {
        var present = SLOTS.filter(function (s) { return mt.some(function (m) { return m.slot === s; }); });
        var color = function (s) { return s === "other" ? P.other : P.c[SLOTS.indexOf(s)]; };
        return {
          grid: grid({ top: 38, right: 18 }), legend: legend(P, present.map(function (s) { return { name: T.slot[s], icon: "circle" }; })),
          tooltip: tooltip(P, "item", null, function (p) {
            var m = p.data.m, r = [{ color: color(m.slot), label: T.slot[m.slot], value: m.time }];
            if (isNum(m.kcal)) r.push({ label: "kcal", value: num(m.kcal) });
            if (isNum(m.protein_g)) r.push({ label: T.macro.protein_g, value: num(m.protein_g) + " g" });
            return tipHtml(fmtDay(m.day, DAY_LONG), r, m.desc);
          }),
          xAxis: xDays(P, keys),
          yAxis: yClock(P, { inverse: true, min: function (v) { return Math.max(0, Math.floor((v.min - 30) / 120) * 120); },
            max: function (v) { return Math.min(1440, Math.ceil((v.max + 30) / 120) * 120); } }),
          series: present.map(function (s) {
            return { name: T.slot[s], type: "scatter", symbolSize: 10, itemStyle: { color: color(s), borderColor: P.surface, borderWidth: 1.5 },
              data: mt.filter(function (m) { return m.slot === s; }).map(function (m) { return { value: [m.day, m.minutes], m: m }; }) };
          })
        };
      },
      table: function () {
        return { head: [T.day, "", "", "kcal"], num: [3],
          rows: mt.map(function (m) { return [fmtDay(m.day, DAY_LONG) + " " + m.time, T.slot[m.slot], m.desc || "", isNum(m.kcal) ? num(m.kcal) : "–"]; }) };
      }
    }, "wide");
    var src = N.protein_sources || [];
    addCard(g, {
      title: T.sources, sub: T.sources_sub, empty: !src.length, emptyText: T.sources_hint, cls: "tall",
      option: function (P) {
        var rev = src.slice().reverse();
        return {
          grid: grid({ top: 4, right: 40 }),
          tooltip: tooltip(P, "item", null, function (p) { var s = rev[p.dataIndex]; return tipHtml(s.name, [{ color: P.c[2], label: T.macro.protein_g, value: num(s.protein_g) + " g" }, { label: "n", value: String(s.n) }]); }),
          xAxis: yVal(P, { type: "value" }),
          yAxis: { type: "category", data: rev.map(function (s) { return s.name; }), axisLine: { show: false }, axisTick: { show: false },
            axisLabel: { color: P.text2, fontSize: 11, width: 110, overflow: "truncate" } },
          series: [{ type: "bar", data: rev.map(function (s) { return s.protein_g; }), barMaxWidth: 14,
            itemStyle: { color: P.c[2], borderRadius: [0, 4, 4, 0] },
            label: { show: true, position: "right", color: P.text2, fontSize: 11, formatter: function (p) { return num(p.value); } } }]
        };
      },
      table: function () { return { head: ["", "g", "n"], num: [1, 2], rows: src.map(function (s) { return [s.name, num(s.protein_g), String(s.n)]; }) }; }
    });

    g = section(root, T.sec_drinks, null);
    var water = days.map(function (d) { return d.logged && d.water_ml > 0 ? d.water_ml / 1000 : null; });
    addCard(g, {
      title: T.water, sub: T.water_sub, empty: !water.some(isNum),
      option: function (P) {
        return { grid: grid({ top: 16 }),
          tooltip: dayTip(P, function (d, i) { return [{ color: P.c[0], label: T.water, value: isNum(water[i]) ? num(water[i], 2) + " L" : "–" }]; }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { axisLabel: { formatter: function (v) { return num(v, 1); } } }),
          series: [bar(T.water, water, P.c[0])] };
      },
      table: function () { return dayTable(days, [{ label: T.water + " (L)", num: true, get: function (d) { return d.logged && d.water_ml > 0 ? num(d.water_ml / 1000, 2) : null; } }]); }
    });
    addCard(g, {
      title: T.coffee, sub: T.coffee_sub, empty: !days.some(function (d) { return d.caffeine_n > 0; }),
      option: function (P) {
        return { grid: grid({ top: 16 }),
          tooltip: dayTip(P, function (d) { var r = [{ color: P.c[3], label: T.coffee, value: d.logged ? num(d.caffeine_n) : "–" }]; if (d.last_caffeine) r.push({ label: T.last, value: d.last_caffeine }); return r; }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { minInterval: 1 }),
          series: [bar(T.coffee, days.map(function (d) { return d.logged ? d.caffeine_n : null; }), P.c[3])] };
      },
      table: function () { return dayTable(days, [{ label: T.coffee, num: true, get: function (d) { return d.logged ? String(d.caffeine_n) : null; } }, { label: T.last, get: function (d) { return d.last_caffeine || null; } }]); }
    });
    var lc = days.map(function (d) { return toMin(d.last_caffeine); });
    addCard(g, {
      title: T.last_coffee, sub: T.last_coffee_sub, empty: !lc.some(isNum),
      option: function (P) {
        return { grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "axis", "line", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), [{ color: P.c[3], label: T.last_coffee, value: d.last_caffeine || "–" }]); }),
          xAxis: xDays(P, keys),
          yAxis: yClock(P, { min: function (v) { return Math.max(0, Math.floor((v.min - 60) / 120) * 120); }, max: function (v) { return Math.min(1440, Math.ceil((v.max + 60) / 120) * 120); } }),
          series: [line(T.last_coffee, lc, P.c[3], { showSymbol: true, smooth: false, lineStyle: { width: 1, color: P.c[3], opacity: 0.35 } })] };
      },
      table: function () { return dayTable(days, [{ label: T.last_coffee, get: function (d) { return d.last_caffeine || null; } }]); }
    });
    var aw = weeksOf(days, function () { return { v: 0 }; }, function (w, d) { w.v += d.alcohol_units || 0; });
    addCard(g, {
      title: T.alcohol, sub: T.alcohol_sub, empty: !aw.some(function (w) { return w.v > 0; }),
      option: function (P) { return weekBars(P, aw, P.c[4], T.units, function (v) { return num(v, 1); }); },
      table: function () { return weekTable(aw, T.units, function (v) { return num(v, 1); }); }
    });
    var mealDays = days.filter(function (d) { return d.logged; });
    var two = mealDays.filter(function (d) { return d.meals >= 2; }).length;
    var nMeals = sum(days.map(function (d) { return d.meals; })), noKcal = sum(days.map(function (d) { return d.meals_missing_kcal; }));
    addCard(g, { title: T.completeness, empty: !mealDays.length, custom: function (card) {
      var st = el("div", "stats");
      var a = el("div", "stat");
      a.appendChild(el("div", "stat-value", mealDays.length ? Math.round(two / mealDays.length * 100) + " %" : "–"));
      a.appendChild(el("div", "stat-label", T.days_2meals + " (" + two + "/" + mealDays.length + ")"));
      var b = el("div", "stat");
      b.appendChild(el("div", "stat-value", String(noKcal)));
      b.appendChild(el("div", "stat-label", T.meals_no_kcal));
      var c = el("div", "stat");
      c.appendChild(el("div", "stat-value", String(nMeals)));
      c.appendChild(el("div", "stat-label", T.meals_logged));
      st.appendChild(a); st.appendChild(b); st.appendChild(c);
      card.appendChild(st);
    } });
  }

  // ------------------------------------------------------------------------------------------
  // tab: kitchen
  // ------------------------------------------------------------------------------------------

  function storageName(s) { return T[s === "pantry" ? "pantry_store" : s] || s || "–"; }

  function renderPantryTable(body, items) {
    var wrap = el("div", "table-wrap static pantry-table");
    var table = el("table"), thead = el("thead"), tr = el("tr");
    [[T.item, ""], [T.status, ""], [T.left, "num hide-xs"], [T.storage, "hide-sm"], [T.expiry, "num"]].forEach(function (h) { tr.appendChild(el("th", h[1] || null, h[0])); });
    thead.appendChild(tr);
    table.appendChild(thead);
    var tb = el("tbody");
    items.forEach(function (it) {
      var row = el("tr"), name = el("td");
      row.setAttribute("data-storage", it.storage || "");
      name.appendChild(el("div", "item-name", it.name || it.item_id));
      var dec = it.unit === "pcs" ? 0 : (it.remaining % 1 ? 1 : 0);
      var qty = isNum(it.remaining) ? num(it.remaining, dec) + (it.unit === "pcs" ? "" : " " + it.unit) : "–";
      var flags = [];
      if (it.opened) flags.push(T.opened);
      if (it.expires_est) flags.push(T.estimated);
      var meta = el("div", "item-meta");
      meta.appendChild(el("span", "show-xs", qty + (flags.length ? " · " : "")));
      meta.appendChild(document.createTextNode(flags.join(" · ")));
      if (flags.length) name.appendChild(meta); else { meta.classList.add("show-xs"); name.appendChild(meta); }
      if ((it.status === "check" || it.status === "discard") && it.check_hint) name.appendChild(el("div", "item-hint", it.check_hint));
      row.appendChild(name);
      var st = el("td");
      st.appendChild(chip(PANTRY_TONE[it.status], T["status_" + it.status] || it.status, PANTRY_ICON[it.status]));
      row.appendChild(st);
      row.appendChild(el("td", "num hide-xs", qty));
      row.appendChild(el("td", "hide-sm", storageName(it.storage)));
      row.appendChild(el("td", "num", expiryText(it.days_left)));
      tb.appendChild(row);
    });
    table.appendChild(tb);
    wrap.appendChild(table);
    body.appendChild(wrap);
    return tb;
  }

  function tabKitchen(root, D) {
    var K = D.tabs.kitchen, pantry = K.pantry || [], cur = K.currency || "EUR";
    var g = section(root, T.sec_pantry, null);
    addCard(g, { title: T.pantry, sub: T.pantry_sub, empty: !pantry.length, custom: function (card) {
      var filters = el("div", "filters");
      filters.setAttribute("role", "group");
      filters.setAttribute("aria-label", T.storage);
      var tb;
      [["all", T.all_storage], ["fridge", T.fridge], ["freezer", T.freezer], ["pantry", T.pantry_store]].forEach(function (f) {
        var n = f[0] === "all" ? pantry.length : pantry.filter(function (p) { return p.storage === f[0]; }).length;
        if (f[0] !== "all" && !n) return;
        var b = el("button", "filter");
        b.type = "button";
        b.setAttribute("aria-pressed", String(f[0] === "all"));
        b.appendChild(document.createTextNode(f[1]));
        b.appendChild(el("span", "count", String(n)));
        b.addEventListener("click", function () {
          filters.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
          tb.querySelectorAll("tr").forEach(function (r) { r.hidden = f[0] !== "all" && r.getAttribute("data-storage") !== f[0]; });
        });
        filters.appendChild(b);
      });
      card.appendChild(filters);
      tb = renderPantryTable(card, pantry);
    } }, "wide");
    // expiry agenda: overdue + next 7 days
    var cols = [{ key: "over", label: T.overdue, items: [] }];
    for (var i = 0; i < 7; i++) {
      var dd = parseDay(D.today);
      dd.setDate(dd.getDate() + i);
      cols.push({ key: i, label: i === 0 ? T.today : i === 1 ? T.tomorrow : new Intl.DateTimeFormat(T.locale, { weekday: "short", day: "numeric" }).format(dd), items: [] });
    }
    pantry.forEach(function (p) {
      if (p.days_left == null) return;
      if (p.days_left < 0) cols[0].items.push(p); else if (p.days_left < 7) cols[p.days_left + 1].items.push(p);
    });
    var anyExp = cols.some(function (c) { return c.items.length; });
    addCard(g, { title: T.timeline, sub: T.timeline_sub, empty: !anyExp, emptyText: T.timeline_none, custom: function (card) {
      var ag = el("ol", "agenda");
      cols.forEach(function (c) {
        var li = el("li", "agenda-day" + (c.items.length ? "" : " empty-day"));
        li.appendChild(el("div", "agenda-label", c.label));
        var box = el("div", "agenda-items");
        if (!c.items.length) box.appendChild(el("span", "muted-text", "–"));
        c.items.forEach(function (p) {
          var m = el("span", "marker " + PANTRY_TONE[p.status]);
          m.title = PANTRY_ICON[p.status] + " " + T["status_" + p.status] + " · " + (p.expires ? fmtDay(p.expires, DAY_SHORT) : "") + " · " + storageName(p.storage);
          m.appendChild(el("i", null, PANTRY_ICON[p.status]));
          m.appendChild(document.createTextNode(p.name));
          m.appendChild(el("span", "sr-only", " (" + T["status_" + p.status] + ")"));
          box.appendChild(m);
        });
        li.appendChild(box);
        ag.appendChild(li);
      });
      card.appendChild(ag);
    } });

    g = section(root, T.sec_money, null, "grid-2");
    var purchases = (K.purchases || []).filter(function (p) { return isNum(p.total_eur); });
    var dayRows = D.days.map(function (d) { return { day: d.day }; });
    var pw = weeksOf(dayRows, function () { return { v: 0 }; }, function (w, d) {
      purchases.forEach(function (p) { if (p.day === d.day) w.v += p.total_eur; });
    });
    addCard(g, {
      title: T.spend_week, sub: T.spend_week_sub, empty: !purchases.length, emptyText: T.prices_hint,
      option: function (P) { return weekBars(P, pw, P.c[0], T.cost.groceries, function (v) { return eur(v, cur); }); },
      table: function () { return weekTable(pw, "€", function (v) { return eur(v, cur); }); }
    });
    var stores = {};
    purchases.forEach(function (p) { var s = p.store || "–"; stores[s] = (stores[s] || 0) + p.total_eur; });
    var storeList = Object.keys(stores).sort(function (a, b) { return stores[b] - stores[a]; });
    addCard(g, {
      title: T.spend_store, sub: T.spend_store_sub, empty: !storeList.length, emptyText: T.prices_hint,
      option: function (P) {
        var rev = storeList.slice().reverse();
        return {
          grid: grid({ top: 4, right: 64 }),
          tooltip: tooltip(P, "item", null, function (p) { return tipHtml(rev[p.dataIndex], [{ color: P.c[0], label: T.cost.groceries, value: eur(p.value, cur) }]); }),
          xAxis: yVal(P, { type: "value" }),
          yAxis: { type: "category", data: rev, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: P.text2, fontSize: 11, width: 110, overflow: "truncate" } },
          series: [{ type: "bar", data: rev.map(function (s) { return Math.round(stores[s] * 100) / 100; }), barMaxWidth: 14,
            itemStyle: { color: P.c[0], borderRadius: [0, 4, 4, 0] },
            label: { show: true, position: "right", color: P.text2, fontSize: 11, formatter: function (p) { return eur(p.value, cur); } } }]
        };
      },
      table: function () { return { head: ["", "€"], num: [1], rows: storeList.map(function (s) { return [s, eur(stores[s], cur)]; }) }; }
    });
    var out = K.eating_out || [];
    var ow = weeksOf(dayRows, function () { return { v: 0, n: 0 }; }, function (w, d) {
      out.forEach(function (o) { if (o.day === d.day) { w.v += o.eur; w.n++; } });
    });
    addCard(g, {
      title: T.eating_out, sub: T.eating_out_sub, empty: !out.length, emptyText: T.eating_out_hint,
      option: function (P) { return weekBars(P, ow, P.c[1], T.cost.out, function (v) { return eur(v, cur); }, { rows: function (w) { return [{ label: "n", value: String(w.n) }]; } }); },
      table: function () {
        return { head: [T.day, "", "€"], num: [2], rows: out.map(function (o) { return [fmtDay(o.day, DAY_LONG) + " " + o.time, o.desc || "", eur(o.eur, cur)]; }) };
      }
    });
    var waste = K.waste || [];
    var months = {};
    waste.forEach(function (w) { var m = (w.day || "").slice(0, 7); if (!m) return; months[m] = months[m] || { eur: 0, n: 0 }; months[m].n++; months[m].eur += w.eur || 0; });
    var mkeys = Object.keys(months).sort();
    addCard(g, {
      title: T.waste, sub: T.waste_sub, empty: !waste.length, emptyText: T.waste_none,
      option: function (P) {
        var s = bar(T.waste, mkeys.map(function (m) { return Math.round(months[m].eur * 100) / 100; }), P.c[1], { barMaxWidth: 28 });
        return { grid: grid({ top: 16 }),
          tooltip: tooltip(P, "axis", "shadow", function (ps) { var m = mkeys[ps[0].dataIndex]; return tipHtml(fmtDay(m + "-01", MONTH), [{ color: P.c[1], label: "€", value: eur(months[m].eur, cur) }, { label: T.waste_items, value: String(months[m].n) }]); }),
          xAxis: xCat(P, mkeys, function (v) { return fmtDay(v + "-01", { month: "short" }); }), yAxis: yVal(P), series: [s] };
      },
      after: function (card) {
        var ul = el("ul", "rows compact");
        waste.slice(0, 6).forEach(function (w) {
          listRow(ul, el("span", "row-dot"), w.name + " · " + (T.reason[w.reason] || w.reason), (w.day ? fmtDay(w.day, DAY_SHORT) + " · " : "") + (isNum(w.eur) ? eur(w.eur, cur) : "–"));
        });
        card.appendChild(ul);
      },
      table: function () { return { head: [T.day, T.item, "", "€"], num: [3], rows: waste.map(function (w) { return [w.day ? fmtDay(w.day, DAY_LONG) : "–", w.name, T.reason[w.reason] || w.reason, isNum(w.eur) ? eur(w.eur, cur) : "–"]; }) }; }
    });

    g = section(root, T.sec_cook, null, "grid-2");
    addCard(g, { title: T.shopping, empty: !K.shopping_list, emptyText: T.shopping_hint, custom: function (card) {
      var md = el("div", "md");
      md.innerHTML = window.BosMarkdown.render(K.shopping_list);
      card.appendChild(md);
    } });
    var cb = K.cookbook || [], rt = K.ratings || {};
    addCard(g, { title: T.cookbook, sub: T.cookbook_sub, empty: !cb.length, custom: function (card) { renderCookbook(card, cb); },
      note: cb.length ? tpl(T.ratings, { up: rt.up || 0, down: rt.down || 0 }) : null });
    var cu = K.cuisines_30d || {}, ckeys = Object.keys(cu);
    addCard(g, {
      title: T.cuisines, sub: T.cuisines_sub, empty: !ckeys.length,
      option: function (P) {
        var rev = ckeys.slice().reverse();
        return {
          grid: grid({ top: 4, right: 28 }),
          tooltip: tooltip(P, "item", null, function (p) { return tipHtml(pretty(rev[p.dataIndex]), [{ color: P.c[2], label: T.dishes, value: String(p.value) }]); }),
          xAxis: yVal(P, { type: "value", minInterval: 1 }),
          yAxis: { type: "category", data: rev.map(pretty), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: P.text2, fontSize: 11 } },
          series: [{ type: "bar", data: rev.map(function (k) { return cu[k]; }), barMaxWidth: 14, itemStyle: { color: P.c[2], borderRadius: [0, 4, 4, 0] } }]
        };
      },
      table: function () { return { head: ["", T.dishes], num: [1], rows: ckeys.map(function (k) { return [pretty(k), String(cu[k])]; }) }; }
    });
    var sk = K.skills || [];
    addCard(g, { title: T.skills, sub: sk.length ? tpl(T.skills_count, { n: sk.length }) : T.skills_sub, empty: !sk.length, emptyText: T.skills_hint,
      custom: function (card) {
        var ol = el("ol", "path");
        sk.forEach(function (s) {
          var li = el("li");
          li.appendChild(el("div", "path-skill", s.skill));
          li.appendChild(el("div", "path-meta", (s.recipe || "") + " · " + fmtDay(s.day, DAY_SHORT)));
          ol.appendChild(li);
        });
        card.appendChild(ol);
      } });
  }

  function stars(n) {
    var s = el("span", "stars");
    s.setAttribute("aria-label", (n || 0) + " / 5");
    for (var i = 1; i <= 5; i++) {
      var x = el("span", i <= (n || 0) ? null : "off", "★");
      x.setAttribute("aria-hidden", "true");
      s.appendChild(x);
    }
    return s;
  }

  function renderCookbook(body, list) {
    var ul = el("ul", "recipes");
    list.forEach(function (r) {
      var li = el("li");
      li.appendChild(el("div", "recipe-name", r.name || "–"));
      var meta = [fmtDay(r.day, DAY_SHORT)];
      if (r.cuisine) meta.push(pretty(r.cuisine));
      meta.push(T[r.status] || r.status || "");
      li.appendChild(el("div", "recipe-meta", meta.filter(Boolean).join(" · ")));
      var sc = el("div", "recipe-scores");
      var a = el("span"); a.title = T.simplicity; a.appendChild(el("span", "sr-only", T.simplicity + " ")); a.appendChild(stars(r.simplicity));
      var b = el("span"); b.title = T.nutrition_score; b.appendChild(el("span", "sr-only", T.nutrition_score + " ")); b.appendChild(stars(r.nutrition_score));
      var rt = el("span", "rating", r.rating === "up" ? "👍" : r.rating === "down" ? "👎" : "–");
      rt.title = T.rating;
      sc.appendChild(a); sc.appendChild(b); sc.appendChild(rt);
      li.appendChild(sc);
      ul.appendChild(li);
    });
    body.appendChild(ul);
    body.appendChild(el("p", "note", "★ " + T.simplicity + " · ★ " + T.nutrition_score + " · 👍/👎 " + T.rating));
  }

  // ------------------------------------------------------------------------------------------
  // tab: sleep & energy
  // ------------------------------------------------------------------------------------------

  function meanBars(P, groups, color) {
    return {
      grid: grid({ top: 16 }),
      tooltip: tooltip(P, "item", null, function (p) { var x = groups[p.dataIndex]; return tipHtml(x.label, [{ color: color, label: T.mean_sleep, value: hm(x.mean) }, { label: "n", value: tpl(T.n_nights, { n: x.n }) }]); }),
      xAxis: xCat(P, groups.map(function (x) { return x.label + "\n(n = " + x.n + ")"; })),
      yAxis: yVal(P, { min: 0, axisLabel: { formatter: function (v) { return v + " h"; } } }),
      series: [{ type: "bar", data: groups.map(function (x) { return x.mean; }), barMaxWidth: 44, itemStyle: { color: color, borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: "top", color: P.text2, fontSize: 11, formatter: function (p) { return isNum(p.value) ? num(p.value, 1) + " h" : ""; } } }]
    };
  }

  function tabSleep(root, D) {
    var S = D.tabs.sleep, days = D.days, keys = days.map(function (d) { return d.day; });
    var col = function (k) { return days.map(function (d) { return isNum(d[k]) ? d[k] : null; }); };
    var g = section(root, T.sec_sleep, null);
    addCard(g, {
      title: T.sleep, sub: T.sleep_sub, empty: !has(days, "sleep_h"),
      option: function (P) {
        var s = bar(T.sleep, col("sleep_h"), P.c[6]);
        s.markLine = refLine(P, 7, "7 h");
        return { grid: grid({ top: 16, right: 36 }),
          tooltip: tooltip(P, "axis", "shadow", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), [{ color: P.c[6], label: T.sleep, value: hm(d.sleep_h) }, { label: T.quality, value: isNum(d.sleep_quality) ? num1(d.sleep_quality) + " / 5" : "–" }, { label: T.wakeups, value: isNum(d.wakeups) ? String(d.wakeups) : "–" }]); }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { min: 0, interval: 2, max: function (v) { return Math.max(10, Math.ceil(v.max / 2) * 2); } }), series: [s] };
      },
      table: function () {
        return dayTable(days, [{ label: T.hours, num: true, get: function (d) { return isNum(d.sleep_h) ? num(d.sleep_h, 1) : null; } },
          { label: T.quality, num: true, get: function (d) { return isNum(d.sleep_quality) ? num(d.sleep_quality, 1) : null; } },
          { label: T.wakeups, num: true, get: function (d) { return isNum(d.wakeups) ? String(d.wakeups) : null; } }]);
      }
    });
    var nights = S.nights || [], nAt = {}, R = S.regularity || {};
    nights.forEach(function (n) { nAt[n.day] = n; });
    addCard(g, {
      title: T.window, sub: T.window_sub, empty: !nights.length, cls: "tall",
      option: function (P) {
        var base = keys.map(function (k) { return nAt[k] ? Math.max(0, nAt[k].bed_min) : null; });
        var span = keys.map(function (k) { return nAt[k] ? Math.min(960, nAt[k].wake_min) - Math.max(0, nAt[k].bed_min) : null; });
        return {
          grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "axis", "shadow", function (ps) {
            var k = keys[ps[0].dataIndex], n = nAt[k];
            return tipHtml(fmtDay(k, DAY_LONG), n ? [{ color: P.c[6], label: T.bed, value: n.bed }, { color: P.c[6], label: T.wake, value: n.wake }, { label: T.sleep, value: hm(n.sleep_h) }] : [{ label: T.sleep, value: "–" }]);
          }),
          xAxis: xDays(P, keys),
          yAxis: yVal(P, { inverse: true, interval: 120,
            min: function (v) { return Math.max(0, Math.floor((v.min - 30) / 120) * 120); }, max: function (v) { return Math.min(960, Math.ceil((v.max + 30) / 120) * 120); },
            axisLabel: { formatter: function (v) { return clock(20 * 60 + v); } } }),
          series: [
            { type: "bar", stack: "n", data: base, itemStyle: { color: "transparent" }, emphasis: { disabled: true }, silent: true, barMaxWidth: 16, barCategoryGap: "28%" },
            { name: T.sleep, type: "bar", stack: "n", data: span, barMaxWidth: 16, itemStyle: { color: P.c[6], borderRadius: 4 } }
          ]
        };
      },
      table: function () { return { head: [T.day, T.bed, T.wake, T.hours], num: [3], rows: nights.map(function (n) { return [fmtDay(n.day, DAY_LONG), n.bed, n.wake, num(n.sleep_h, 1)]; }) }; }
    }, "wide");
    addCard(g, { title: T.regularity_t, sub: tpl(T.n_nights, { n: R.n || 0 }), empty: !nights.length, custom: function (card) {
      var st = el("div", "stats");
      [[R.bed_mean || "–", T.bed_mean], [R.wake_mean || "–", T.wake_mean], [isNum(R.bed_sd_min) ? "±" + num(R.bed_sd_min) + " min" : "–", T.bed_sd]].forEach(function (x) {
        var d = el("div", "stat");
        d.appendChild(el("div", "stat-value", x[0]));
        d.appendChild(el("div", "stat-label", x[1]));
        st.appendChild(d);
      });
      card.appendChild(st);
      card.appendChild(el("p", "note", T.regularity_note));
    } });
    addCard(g, {
      title: T.quality, sub: T.quality_sub, empty: !has(days, "sleep_quality"),
      option: function (P) {
        return { grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "axis", "line", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), [{ color: P.c[6], label: T.quality, value: isNum(d.sleep_quality) ? num1(d.sleep_quality) + " / 5" : "–" }]); }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { min: 1, max: 5, interval: 1 }),
          series: [line(T.quality, col("sleep_quality"), P.c[6], { smooth: false })] };
      },
      table: function () { return dayTable(days, [{ label: T.quality, num: true, get: function (d) { return isNum(d.sleep_quality) ? num(d.sleep_quality, 1) : null; } }]); }
    });
    addCard(g, {
      title: T.wakeups, sub: T.wakeups_sub, empty: !has(days, "wakeups"),
      option: function (P) {
        return { grid: grid({ top: 16 }),
          tooltip: tooltip(P, "axis", "shadow", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), [{ color: P.c[6], label: T.wakeups, value: isNum(d.wakeups) ? String(d.wakeups) : "–" }]); }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { minInterval: 1 }), series: [bar(T.wakeups, col("wakeups"), P.c[6])] };
      },
      table: function () { return dayTable(days, [{ label: T.wakeups, num: true, get: function (d) { return isNum(d.wakeups) ? String(d.wakeups) : null; } }]); }
    });

    g = section(root, T.sec_factors, T.sec_factors_sub, "grid-2");
    var svu = S.vs_last_use || [];
    if (D.tabs.substances.active) addCard(g, {
      title: T.svu, sub: T.svu_sub, empty: !svu.some(function (r) { return r.last_use_prev_evening; }), note: tpl(T.hypothesis, { n: svu.length }),
      option: function (P, w) {
        var seen = {};
        var pt = function (r) {
          var x = r.minutes_after_18 == null ? -60 : r.minutes_after_18;
          var k = x + "|" + r.sleep_h, n = seen[k] = (seen[k] || 0) + 1;
          return { value: [x + (n === 1 ? 0 : (n % 2 ? -1 : 1) * Math.ceil((n - 1) / 2) * 9), r.sleep_h], r: r };
        };
        var dot = function (c) { return { color: c, borderColor: P.surface, borderWidth: 1.5 }; };
        return {
          grid: grid({ top: 36, right: 18 }), legend: legend(P, [{ name: T.svu_use, icon: "circle" }, { name: T.svu_none, icon: "circle" }]),
          tooltip: tooltip(P, "item", null, function (p) { var r = p.data.r; return tipHtml(fmtDay(r.day, DAY_LONG), [{ color: p.color, label: T.last_use, value: r.last_use_prev_evening || T.no_use }, { label: T.sleep, value: hm(r.sleep_h) }]); }),
          xAxis: { type: "value", min: -90, max: 540, interval: 30, axisLine: { show: true, lineStyle: { color: P.axis } }, axisTick: { show: false }, splitLine: { show: false },
            axisLabel: { color: P.text2, fontSize: 11, margin: 10, formatter: function (v) {
              if (v === -60) return T.none;
              var step = w < 520 ? 180 : 120;
              if (v < 0 || v % step !== 0 || (w < 520 && v === 0)) return "";
              return clock(18 * 60 + v);
            } } },
          yAxis: yVal(P, { scale: true, minInterval: 0.5, axisLabel: { formatter: function (v) { return num1(v) + " h"; } } }),
          series: [
            { name: T.svu_use, type: "scatter", data: svu.filter(function (r) { return r.minutes_after_18 != null; }).map(pt), symbolSize: 10, itemStyle: dot(P.c[0]),
              markLine: { silent: true, symbol: "none", animation: false, label: { show: false }, lineStyle: { color: P.grid, type: "solid", width: 1 }, data: [{ xAxis: -25 }] } },
            { name: T.svu_none, type: "scatter", data: svu.filter(function (r) { return r.minutes_after_18 == null; }).map(pt), symbolSize: 10, itemStyle: dot(P.c[1]) }
          ]
        };
      },
      table: function () { return { head: [T.day, T.last_use, T.hours], num: [2], rows: svu.map(function (r) { return [fmtDay(r.day, DAY_LONG), r.last_use_prev_evening || T.no_use, num(r.sleep_h, 1)]; }) }; }
    });
    var vc = S.vs_coffee || [];
    addCard(g, {
      title: T.vs_coffee, sub: T.vs_coffee_sub, empty: vc.length < 2, note: tpl(T.hypothesis, { n: vc.length }),
      option: function (P) {
        return {
          grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "item", null, function (p) { var r = p.data.r; return tipHtml(fmtDay(r.day, DAY_LONG), [{ color: P.c[3], label: T.last_coffee, value: r.last_coffee }, { label: T.sleep, value: hm(r.sleep_h) }]); }),
          xAxis: { type: "value", min: function (v) { return Math.floor((v.min - 60) / 120) * 120; }, max: function (v) { return Math.ceil((v.max + 60) / 120) * 120; }, interval: 120,
            axisLine: { show: true, lineStyle: { color: P.axis } }, axisTick: { show: false }, splitLine: { show: false },
            axisLabel: { color: P.text2, fontSize: 11, formatter: function (v) { return clock(v); } } },
          yAxis: yVal(P, { scale: true, minInterval: 0.5, axisLabel: { formatter: function (v) { return num1(v) + " h"; } } }),
          series: [{ type: "scatter", symbolSize: 10, itemStyle: { color: P.c[3], borderColor: P.surface, borderWidth: 1.5 },
            data: vc.map(function (r) { return { value: [r.minutes, r.sleep_h], r: r }; }) }]
        };
      },
      table: function () { return { head: [T.day, T.last_coffee, T.hours], num: [2], rows: vc.map(function (r) { return [fmtDay(r.day, DAY_LONG), r.last_coffee, num(r.sleep_h, 1)]; }) }; }
    });
    var va = S.vs_alcohol || {}, vt = S.vs_training || {};
    var ag = [{ label: T.no_alcohol, mean: (va.none || {}).mean, n: (va.none || {}).n || 0 }, { label: T.some_alcohol, mean: (va.some || {}).mean, n: (va.some || {}).n || 0 }];
    var tg = [{ label: T.rest_day, mean: (vt.rest || {}).mean, n: (vt.rest || {}).n || 0 }, { label: T.training_day, mean: (vt.training || {}).mean, n: (vt.training || {}).n || 0 }];
    addCard(g, {
      title: T.vs_alcohol, sub: T.vs_alcohol_sub, empty: !ag[1].n || !ag[0].n, note: tpl(T.hypothesis, { n: ag[0].n + ag[1].n }),
      option: function (P) { return meanBars(P, ag, P.c[4]); },
      table: function () { return { head: ["", T.mean_sleep, "n"], num: [1, 2], rows: ag.map(function (x) { return [x.label, hm(x.mean), String(x.n)]; }) }; }
    });
    addCard(g, {
      title: T.vs_training, sub: T.vs_training_sub, empty: !tg[1].n || !tg[0].n, note: tpl(T.hypothesis, { n: tg[0].n + tg[1].n }),
      option: function (P) { return meanBars(P, tg, P.c[0]); },
      table: function () { return { head: ["", T.mean_sleep, "n"], num: [1, 2], rows: tg.map(function (x) { return [x.label, hm(x.mean), String(x.n)]; }) }; }
    });

    g = section(root, T.sec_mind, null);
    var mindKeys = [["energy", T.energy], ["mood", T.mood], ["stress", T.stress]];
    addCard(g, {
      title: T.mind, sub: T.mind_sub, empty: !mindKeys.some(function (k) { return has(days, k[0]); }),
      option: function (P, w) {
        var wide = w >= 520;
        var ends = mindKeys.map(function (k) { var c = col(k[0]); for (var j = c.length - 1; j >= 0; j--) if (isNum(c[j])) return j + ":" + c[j]; return null; });
        return {
          grid: grid({ top: 36, right: wide ? 112 : 14 }), legend: legend(P, mindKeys.map(function (k) { return { name: k[1], icon: LINE_ICON }; })),
          tooltip: tooltip(P, "axis", "line", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), mindKeys.map(function (k, i) { return { color: P.c[i], label: k[1], value: isNum(d[k[0]]) ? num1(d[k[0]]) : "–" }; })); }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { min: 1, max: 5, interval: 1 }),
          series: mindKeys.map(function (k, i) {
            // lines ending on the same value share one end label instead of overlapping
            var text = null;
            if (wide && ends[i] !== null && ends.indexOf(ends[i]) === i) text = mindKeys.filter(function (_, j) { return ends[j] === ends[i]; }).map(function (m) { return m[1]; }).join(" · ");
            return line(k[1], text ? lastLabel(col(k[0]), { formatter: text, color: P.text2, fontSize: 11 }) : col(k[0]), P.c[i]);
          })
        };
      },
      table: function () { return dayTable(days, mindKeys.map(function (k) { return { label: k[1], num: true, get: function (d) { return isNum(d[k[0]]) ? num(d[k[0]], 1) : null; } }; })); }
    }, "full");
  }

  // ------------------------------------------------------------------------------------------
  // tab: substances
  // ------------------------------------------------------------------------------------------

  function tabSubstances(root, D) {
    var U = D.tabs.substances, days = D.days, keys = days.map(function (d) { return d.day; });
    if (!U.active) {
      var g0 = section(root, null, null);
      addCard(g0, { title: T.tab.substances, empty: true, emptyText: T.substances_inactive }, "full");
      return;
    }
    var st = U.streaks || {}, bl = U.baseline;
    var tiles = section(root, T.sec_progress, null, "kpis");
    kpi(tiles, { label: T.free_days, value: String(st.free_days || 0), sub: tpl(T.free_days_sub, { n: st.logged_days || 0 }) });
    kpi(tiles, { label: T.streak, value: String(st.current || 0), unit: T.streak_unit });
    kpi(tiles, { label: T.streak_longest, value: String(st.longest || 0), unit: T.streak_unit });
    kpi(tiles, { label: T.baseline, value: bl ? num(bl.per_day, 1) : "–", unit: T.per_day_unit, sub: bl ? tpl(T.baseline_sub, { name: bl.name }) : tpl(T.setting_hint, { key: "phases" }) });
    var pb = U.plan_b;
    if (pb) {
      var tile = kpi(tiles, { label: T.planb, value: isNum(pb.pct_of_baseline) ? num(pb.pct_of_baseline) + " %" : "–",
        sub: tpl(T.planb_sub, { name: pb.phase_name, d: pb.day, w: pb.window_days }) });
      tile.classList.add("planb");
      var ptone = { on_track: "good", watch: "warning", plan_b_due: "serious" };
      if (pb.status) tile.insertBefore(chip(ptone[pb.status], T.planb_status[pb.status]), tile.querySelector(".kpi-sub"));
      else tile.appendChild(el("div", "kpi-sub", T.planb_wait));
      tile.appendChild(el("div", "kpi-foot", (isNum(pb.current_per_day) ? tpl(T.planb_now, { n: pb.current_days }) + ": " + num(pb.current_per_day, 1) + " " + T.per_day_unit + " · " : "") +
        tpl(T.planb_thr, { t: pb.threshold_pct, w: pb.window_days })));
    }

    var g = section(root, null, null, "grid-2");
    var tgt = U.target_per_day;
    addCard(g, {
      title: T.tob, sub: T.tob_sub, empty: !days.some(function (d) { return d.substance_n > 0; }),
      option: function (P) {
        var w = bar(T.with_tob, days.map(function (d) { return d.logged ? d.tobacco_n : null; }), P.c[0], { stack: "t", itemStyle: { color: P.c[0], borderColor: P.surface, borderWidth: 1 } });
        var wo = bar(T.without_tob, days.map(function (d) { return d.logged ? d.substance_n - d.tobacco_n : null; }), P.c[1], { stack: "t" });
        var ml = [];
        if (bl) ml.push({ yAxis: bl.per_day, label: { formatter: T.baseline + " " + num(bl.per_day, 1) } });
        if (isNum(tgt)) ml.push({ yAxis: tgt, label: { formatter: T.phase_target + " " + num1(tgt) } });
        if (ml.length) w.markLine = { silent: true, symbol: "none", animation: false, lineStyle: { color: P.text2, type: [4, 4], width: 1, opacity: 0.8 },
          label: { show: true, position: "insideEndTop", color: P.text2, fontSize: 11 }, data: ml };
        return {
          grid: grid({ top: 38 }), legend: legend(P, [T.with_tob, T.without_tob]),
          tooltip: tooltip(P, "axis", "shadow", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), [{ color: P.c[0], label: T.with_tob, value: String(d.tobacco_n) }, { color: P.c[1], label: T.without_tob, value: String(d.substance_n - d.tobacco_n) }]); }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { minInterval: 1, max: function (v) { return Math.max(v.max, bl ? Math.ceil(bl.per_day) + 1 : 0); } }), series: [w, wo]
        };
      },
      table: function () { return dayTable(days, [{ label: T.with_tob, num: true, get: function (d) { return d.logged ? String(d.tobacco_n) : null; } }, { label: T.without_tob, num: true, get: function (d) { return d.logged ? String(d.substance_n - d.tobacco_n) : null; } }]); }
    });

    var order = (U.trigger_order || []).slice(0, 6), totals = U.triggers_total || {};
    var named = order.filter(function (t) { return totals[t]; });
    var otherSum = function (d) { var s = 0; Object.keys(d.triggers || {}).forEach(function (t) { if (order.indexOf(t) < 0) s += d.triggers[t]; }); return s; };
    var hasOther = days.some(function (d) { return otherSum(d) > 0; });
    var trigColor = function (P, t) { return t === null ? P.other : P.c[order.indexOf(t)]; };
    addCard(g, {
      title: T.trig, sub: T.trig_sub, empty: !days.some(function (d) { return d.substance_n > 0; }),
      option: function (P) {
        var groups = named.map(function (t) { return { name: trig(t), color: trigColor(P, t), get: function (d) { return (d.triggers || {})[t] || 0; } }; });
        if (hasOther) groups.push({ name: T.other, color: P.other, get: otherSum });
        var topIdx = days.map(function (d) { var top = -1; groups.forEach(function (gr, i) { if (gr.get(d) > 0) top = i; }); return top; });
        return {
          grid: grid({ top: 38 }), legend: legend(P, groups.map(function (gr) { return gr.name; }), true),
          tooltip: tooltip(P, "axis", "shadow", function (ps) {
            var d = days[ps[0].dataIndex];
            var rows = ps.filter(function (p) { return p.value > 0 || (p.value && p.value.value > 0); }).reverse().map(function (p) { return { color: p.color, label: p.seriesName, value: String(isNum(p.value) ? p.value : p.value.value) }; });
            rows.push({ label: T.total, value: String(d.substance_n) });
            return tipHtml(fmtDay(d.day, DAY_LONG), rows, d.substance_n ? T.tobacco + ": " + d.tobacco_n + (d.last_substance ? " · " + T.last + " " + d.last_substance : "") : null);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { minInterval: 1 }),
          series: groups.map(function (gr, gi) {
            return { name: gr.name, type: "bar", stack: "use", barMaxWidth: 16, barCategoryGap: "28%", itemStyle: { color: gr.color, borderColor: P.surface, borderWidth: 1 }, emphasis: { focus: "series" },
              data: days.map(function (d, i) { var v = d.logged ? gr.get(d) : null; return topIdx[i] === gi ? { value: v, itemStyle: { borderRadius: [4, 4, 0, 0] } } : v; }) };
          })
        };
      },
      table: function () {
        var cols = named.map(function (t) { return { label: trig(t), num: true, get: function (d) { return d.substance_n ? String((d.triggers || {})[t] || 0) : null; } }; });
        if (hasOther) cols.push({ label: T.other, num: true, get: function (d) { return d.substance_n ? String(otherSum(d)) : null; } });
        cols.push({ label: T.total, num: true, get: function (d) { return d.substance_n ? String(d.substance_n) : null; } });
        return dayTable(days, cols);
      }
    });
    var fu = days.map(function (d) { return toMin(d.first_substance); });
    addCard(g, {
      title: T.first_use, sub: T.first_use_sub, empty: !fu.some(isNum),
      option: function (P) {
        return { grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "axis", "line", function (ps) { var d = days[ps[0].dataIndex]; return tipHtml(fmtDay(d.day, DAY_LONG), [{ color: P.c[0], label: T.first, value: d.first_substance || "–" }]); }),
          xAxis: xDays(P, keys),
          yAxis: yClock(P, { min: function (v) { return Math.max(0, Math.floor((v.min - 60) / 120) * 120); }, max: function (v) { return Math.min(1440, Math.ceil((v.max + 60) / 120) * 120); } }),
          series: [line(T.first, fu, P.c[0], { smooth: false, showSymbol: true })] };
      },
      table: function () { return dayTable(days, [{ label: T.first, get: function (d) { return d.first_substance || null; } }]); }
    });
    var shareKeys = named.slice();
    var shareTotal = sum(Object.keys(totals).map(function (k) { return totals[k]; }));
    var otherTot = shareTotal - sum(shareKeys.map(function (k) { return totals[k]; }));
    addCard(g, {
      title: T.share, sub: T.share_sub, empty: !shareTotal, chartCls: "chart-bar",
      option: function (P) {
        var parts = shareKeys.map(function (t) { return { name: trig(t), value: totals[t], color: trigColor(P, t) }; });
        if (otherTot > 0) parts.push({ name: T.other, value: otherTot, color: P.other });
        return shareBar(P, parts, function (x) { return x.value + T.uses + " · " + Math.round(x.value / shareTotal * 100) + " %"; });
      },
      after: function (card) {
        var ul = el("ul", "legend-list");
        shareKeys.concat(otherTot > 0 ? [null] : []).forEach(function (t) {
          var li = el("li"), dot = el("span", "dot"), v = t === null ? otherTot : totals[t];
          dot.style.background = t === null ? "var(--other)" : "var(--c" + (order.indexOf(t) + 1) + ")";
          li.appendChild(dot);
          li.appendChild(el("span", "ll-label", t === null ? T.other : trig(t)));
          li.appendChild(el("span", "ll-value", Math.round(v / shareTotal * 100) + " %"));
          ul.appendChild(li);
        });
        card.appendChild(ul);
      },
      table: function () { return { head: ["", T.uses, "%"], num: [1, 2], rows: Object.keys(totals).map(function (t) { return [trig(t), String(totals[t]), Math.round(totals[t] / shareTotal * 100) + " %"]; }) }; }
    });
    var ut = U.use_times || [];
    addCard(g, {
      title: T.heat, sub: T.heat_sub, empty: !ut.length, cls: "tall",
      option: function (P, w) {
        var counts = {}, max = 1;
        ut.forEach(function (u) { counts[u.weekday + "|" + u.hour] = u.count; max = Math.max(max, u.count); });
        var zeros = [], vals = [];
        for (var wd = 0; wd < 7; wd++) for (var h = 0; h < 24; h++) { var c = counts[wd + "|" + h]; (c ? vals : zeros).push([h, wd, c || 0]); }
        var cell = { borderColor: P.surface, borderWidth: w < 520 ? 1 : 2, borderRadius: 3 };
        return {
          grid: grid({ top: 6, bottom: 44, right: 4 }),
          tooltip: tooltip(P, "item", null, function (p) { var h = p.value[0]; return tipHtml(T.weekdays[p.value[1]] + " · " + h + ":00–" + (h + 1) + ":00", [{ color: p.value[2] ? p.color : null, label: "", value: p.value[2] + T.uses }]); }),
          xAxis: { type: "category", data: Array.from({ length: 24 }, function (_, i) { return String(i); }), axisLine: { show: false }, axisTick: { show: false }, splitArea: { show: false }, axisLabel: { color: P.text2, fontSize: 11, interval: w < 520 ? 5 : 2 } },
          yAxis: { type: "category", data: T.weekdays, inverse: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: P.text2, fontSize: 11 } },
          visualMap: { type: "continuous", seriesIndex: 1, min: 1, max: max, calculable: false, orient: "horizontal", right: 0, bottom: 0, itemWidth: 10, itemHeight: 120, text: [T.more, T.less], textGap: 8, textStyle: { color: P.text2, fontSize: 11 }, inRange: { color: P.seq.slice(1) } },
          series: [{ type: "heatmap", data: zeros, itemStyle: Object.assign({ color: P.cell }, cell), emphasis: { disabled: true } },
            { type: "heatmap", data: vals, itemStyle: cell, emphasis: { itemStyle: { borderColor: P.text, borderWidth: 1 } } }]
        };
      },
      table: function () { return { head: [T.day, T.hour, T.uses], num: [1, 2], rows: ut.slice().sort(function (a, b) { return b.count - a.count; }).map(function (u) { return [T.weekdays[u.weekday], u.hour + ":00", String(u.count)]; }) }; }
    }, "wide");

    // costs
    var C = U.cost || {}, cur = C.currency || "EUR", cats = C.categories || [];
    g = section(root, T.sec_costs, null);
    var monthsC = (C.per_month || []).filter(function (m) { return cats.some(function (c) { return m[c] && m[c].eur > 0; }); });
    var hint = C.missing && C.missing.length ? tpl(T.costs_hint, { keys: C.missing.join(", ") }) : null;
    var catColor = function (P, c) { return P.c[COSTS.indexOf(c)]; };
    if (C.saved) {
      var sv = C.saved;
      addCard(g, { title: tpl(T.saved, { name: sv.phase_name }), cls: "saved-card", custom: function (card) {
        card.appendChild(el("div", "big-num", "≈ " + eur(sv.eur, cur)));
        card.appendChild(el("p", "note", tpl(T.saved_sub, { b: num(sv.baseline_per_day, 1), c: num(sv.per_day, 1), n: sv.days, p: eur(C.tobacco_eur_per_use, cur) })));
      } });
    }
    addCard(g, {
      title: T.costs_month, sub: T.costs_month_sub, empty: !monthsC.length, emptyText: hint || T.empty,
      note: hint && monthsC.length ? hint : null,
      option: function (P) {
        return {
          grid: grid({ top: 38 }), legend: legend(P, cats.map(function (c) { return T.cost[c]; })),
          tooltip: tooltip(P, "axis", "shadow", function (ps) {
            var m = monthsC[ps[0].dataIndex];
            return tipHtml(fmtDay(m.month + "-01", MONTH), cats.map(function (c) { return { color: catColor(P, c), label: T.cost[c], value: (m[c].est ? "≈ " : "") + eur(m[c].eur, cur) }; }));
          }),
          xAxis: xCat(P, monthsC.map(function (m) { return m.month; }), function (v) { return fmtDay(v + "-01", { month: "short" }); }),
          yAxis: yVal(P),
          series: cats.map(function (c) { return bar(T.cost[c], monthsC.map(function (m) { return m[c].eur; }), catColor(P, c), { stack: "c", barMaxWidth: 32, itemStyle: { color: catColor(P, c), borderColor: P.surface, borderWidth: 1 } }); })
        };
      },
      table: function () { return { head: [T.month].concat(cats.map(function (c) { return T.cost[c]; })), num: cats.map(function (_, i) { return i + 1; }), rows: monthsC.map(function (m) { return [fmtDay(m.month + "-01", MONTH)].concat(cats.map(function (c) { return (m[c].est ? "≈ " : "") + eur(m[c].eur, cur); })); }) }; }
    }, C.saved ? "" : "wide");
    var cdays = C.days || [];
    var cw = weeksOf(cdays, function () { var o = { v: 0 }; cats.forEach(function (c) { o[c] = 0; }); return o; }, function (w, d) { cats.forEach(function (c) { w[c] += d[c] || 0; w.v += d[c] || 0; }); });
    addCard(g, {
      title: T.costs_week, sub: T.costs_week_sub, empty: !cw.some(function (w) { return w.v > 0; }), emptyText: hint || T.empty,
      option: function (P) {
        return {
          grid: grid({ top: 38 }), legend: legend(P, cats.map(function (c) { return T.cost[c]; })),
          tooltip: tooltip(P, "axis", "shadow", function (ps) { var w = cw[ps[0].dataIndex]; return tipHtml(weekRange(w), cats.map(function (c) { return { color: catColor(P, c), label: T.cost[c], value: "≈ " + eur(w[c], cur) }; })); }),
          xAxis: xCat(P, cw.map(weekName)), yAxis: yVal(P),
          series: cats.map(function (c) { return bar(T.cost[c], cw.map(function (w) { return Math.round(w[c] * 100) / 100; }), catColor(P, c), { stack: "c", barMaxWidth: 28, itemStyle: { color: catColor(P, c), borderColor: P.surface, borderWidth: 1 } }); })
        };
      },
      table: function () { return { head: [T.week].concat(cats.map(function (c) { return T.cost[c]; })), num: cats.map(function (_, i) { return i + 1; }), rows: cw.map(function (w) { return [weekRange(w)].concat(cats.map(function (c) { return eur(w[c], cur); })); }) }; }
    });
  }

  // ------------------------------------------------------------------------------------------
  // tab: training
  // ------------------------------------------------------------------------------------------

  function tabTraining(root, D) {
    var TR = D.tabs.training, days = D.days, keys = days.map(function (d) { return d.day; });
    var g = section(root, T.sec_sessions, null);
    var cal = TR.calendar || { sessions: [] }, CATS = ["strength", "endurance", "other"];
    var byDay = {};
    cal.sessions.forEach(function (s) { (byDay[s.day] = byDay[s.day] || []).push(s); });
    addCard(g, {
      title: T.calendar, sub: T.calendar_sub, empty: !cal.sessions.length, cls: "calendar-card",
      option: function (P, w) {
        var from = parseDay(cal.from), to = parseDay(cal.to), all = [];
        for (var d = new Date(from); d <= to; d.setDate(d.getDate() + 1)) all.push([d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()), 0]);
        var weeks = Math.ceil((daysBetween(cal.from, cal.to) + 1) / 7) + 1;
        var ch = 26, cw = Math.max(ch * 0.6, Math.min(ch * 2.4, Math.floor((w - 44) / weeks)));
        var catOf = function (list) { for (var i = 0; i < CATS.length; i++) if (list.some(function (s) { return s.category === CATS[i]; })) return CATS[i]; return "other"; };
        var months = [];
        for (var m = 0; m < 12; m++) months.push(new Intl.DateTimeFormat(T.locale, { month: "short" }).format(new Date(2026, m, 1)));
        return {
          legend: legend(P, CATS.filter(function (c) { return cal.sessions.some(function (s) { return s.category === c; }); }).map(function (c) { return { name: T.cat[c], icon: "roundRect" }; })),
          tooltip: tooltip(P, "item", null, function (p) {
            var list = byDay[p.value[0]] || [];
            return tipHtml(fmtDay(p.value[0], DAY_LONG), list.length ? list.map(function (s) { return { color: P.c[CATS.indexOf(s.category)], label: T.cat[s.category] + (s.plan ? " " + s.plan : "") + " · " + what(s.kind), value: isNum(s.dur_min) ? s.dur_min + " min" : "" }; }) : [{ label: "", value: "–" }]);
          }),
          calendar: { top: 50, left: 34, cellSize: [cw, ch], range: [cal.from, cal.to], orient: "horizontal",
            splitLine: { show: false }, itemStyle: { color: "transparent", borderColor: P.surface, borderWidth: 3 },
            yearLabel: { show: false }, dayLabel: { firstDay: 1, nameMap: [T.weekdays[6]].concat(T.weekdays.slice(0, 6)), color: P.text2, fontSize: 10, margin: 6 },
            monthLabel: { nameMap: months, color: P.text2, fontSize: 11, margin: 6 } },
          series: [{ type: "heatmap", coordinateSystem: "calendar", data: all, itemStyle: { color: P.cell, borderColor: P.surface, borderWidth: 2, borderRadius: 3 }, emphasis: { disabled: true }, silent: false }]
            .concat(CATS.map(function (c, i) {
              return { name: T.cat[c], type: "scatter", coordinateSystem: "calendar", symbol: "roundRect", symbolSize: [cw - 5, ch - 5],
                itemStyle: { color: P.c[i], borderRadius: 3 },
                data: Object.keys(byDay).filter(function (k) { return catOf(byDay[k]) === c; }).map(function (k) { return [k, byDay[k].length]; }) };
            }))
        };
      },
      table: function () { return { head: [T.day, "", T.minutes], num: [2], rows: cal.sessions.map(function (s) { return [fmtDay(s.day, DAY_LONG), T.cat[s.category] + (s.plan ? " " + s.plan : "") + " · " + what(s.kind), isNum(s.dur_min) ? String(s.dur_min) : "–"]; }) }; }
    }, "wide");
    var plan = TR.plan || 4;
    var tw = weeksOf(days, function () { return { v: 0, min: 0 }; }, function (w, d) { w.v += d.training_n || 0; w.min += d.training_min || 0; });
    addCard(g, {
      title: T.train, sub: T.train_sub, empty: !days.some(function (d) { return d.training_n > 0; }),
      option: function (P) { return weekBars(P, tw, P.c[0], T.sessions, function (v) { return v + " / " + plan; }, { ref: plan, refLabel: T.plan + " " + plan, y: { minInterval: 1, max: function (v) { return Math.max(plan + 1, v.max); } }, rows: function (w) { return [{ label: T.minutes, value: num(w.min) }]; } }); },
      table: function () { return weekTable(tw, T.sessions, function (v) { return v + " / " + plan; }); }
    });

    g = section(root, T.sec_strength, null);
    var lifts = (TR.lifts && TR.lifts.exercises) || {}, exs = Object.keys(lifts).slice(0, 4), others = (TR.lifts && TR.lifts.others) || [];
    var liftAt = {};
    exs.forEach(function (ex) { liftAt[ex] = {}; lifts[ex].forEach(function (p) { liftAt[ex][p.day] = p; }); });
    addCard(g, {
      title: T.lifts, sub: T.lifts_sub, empty: !exs.length, note: others.length ? T.others + ": " + others.join(", ") : null,
      option: function (P) {
        return {
          grid: grid({ top: 36, right: 18 }), legend: legend(P, exs.map(function (ex) { return { name: ex, icon: LINE_ICON }; }), exs.length > 3),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var d = keys[ps[0].dataIndex];
            return tipHtml(fmtDay(d, DAY_LONG), exs.filter(function (ex) { return liftAt[ex][d]; }).map(function (ex) {
              var p = liftAt[ex][d];
              return { color: P.c[exs.indexOf(ex)], label: ex, value: T.e1rm + " " + num(p.e1rm) + " kg · " + num1(p.top_kg) + " × " + (p.top_reps || "–") };
            }));
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(2)),
          series: exs.map(function (ex, i) { return line(ex, keys.map(function (k) { return liftAt[ex][k] ? liftAt[ex][k].e1rm : null; }), P.c[i], { showSymbol: true, smooth: false }); })
        };
      },
      table: function () {
        var rows = [];
        exs.forEach(function (ex) { lifts[ex].forEach(function (p) { rows.push([fmtDay(p.day, DAY_LONG), ex, num(p.e1rm, 1), num1(p.top_kg) + " × " + (p.top_reps || "–")]); }); });
        return { head: [T.day, T.exercise, T.e1rm, T.top_set], num: [2, 3], rows: rows };
      }
    }, "wide");
    var volAt = {};
    (TR.volume || []).forEach(function (v) { volAt[v.day] = v.kg; });
    var vw = weeksOf(days, function () { return { v: 0 }; }, function (w, d) { w.v += volAt[d.day] || 0; });
    addCard(g, {
      title: T.volume, sub: T.volume_sub, empty: !(TR.volume || []).length,
      option: function (P) { return weekBars(P, vw, P.c[0], T.volume, function (v) { return num(v) + " kg"; }); },
      table: function () { return weekTable(vw, "kg", function (v) { return num(v); }); }
    });

    g = section(root, T.sec_endurance, null);
    var en = TR.endurance || [];
    var enAt = {};
    en.forEach(function (e) { (enAt[e.day] = enAt[e.day] || []).push(e); });
    var ew = weeksOf(days, function () { return { v: 0, n: 0, km: 0 }; }, function (w, d) { (enAt[d.day] || []).forEach(function (e) { w.v += e.dur_min || 0; w.n++; w.km += e.distance_km || 0; }); });
    addCard(g, {
      title: T.end_min, sub: T.end_min_sub, empty: !en.length,
      option: function (P) { return weekBars(P, ew, P.c[1], T.minutes, function (v) { return num(v) + " min"; }, { rows: function (w) { return [{ label: T.sessions, value: String(w.n) }, { label: T.distance, value: num(w.km, 1) + " km" }]; } }); },
      table: function () { return weekTable(ew, T.minutes, function (v) { return num(v); }); }
    });
    var paced = en.filter(function (e) { return isNum(e.pace_min_km); });
    var usePace = paced.length > 0, hrS = en.filter(function (e) { return isNum(e.avg_hr); });
    var paceFmt = function (v) { var m = Math.floor(v), s = Math.round((v - m) * 60); if (s === 60) { m++; s = 0; } return m + ":" + pad2(s) + " min/km"; };
    addCard(g, {
      title: usePace ? T.pace : T.avg_hr, sub: usePace ? T.pace_sub : T.avg_hr_sub, empty: !(usePace ? paced : hrS).length,
      option: function (P) {
        var list = usePace ? paced : hrS;
        return {
          grid: grid({ top: 16, right: 18 }),
          tooltip: tooltip(P, "item", null, function (p) {
            var e = list[p.dataIndex], r = [];
            if (isNum(e.pace_min_km)) r.push({ color: P.c[1], label: T.pace, value: paceFmt(e.pace_min_km) });
            if (isNum(e.distance_km)) r.push({ label: T.distance, value: num(e.distance_km, 1) + " km" });
            if (isNum(e.dur_min)) r.push({ label: T.minutes, value: String(e.dur_min) });
            if (isNum(e.avg_hr)) r.push({ label: T.avg_hr, value: e.avg_hr + " /min" });
            return tipHtml(fmtDay(e.day, DAY_LONG) + " · " + what(e.kind), r);
          }),
          xAxis: xCat(P, list.map(function (e) { return e.day; }), function (v) { return fmtDay(v, DAY_AXIS); }),
          yAxis: yVal(P, Object.assign(pad(usePace ? 0.2 : 3), usePace ? { axisLabel: { showMinLabel: false, showMaxLabel: false, formatter: function (v) { return paceFmt(v).replace(" min/km", ""); } } } : {})),
          series: [line(usePace ? T.pace : T.avg_hr, list.map(function (e) { return usePace ? e.pace_min_km : e.avg_hr; }), P.c[1], { smooth: false, showSymbol: true })]
        };
      },
      table: function () { return { head: [T.day, "", T.distance, T.minutes, T.pace, T.avg_hr], num: [2, 3, 4, 5], rows: en.map(function (e) { return [fmtDay(e.day, DAY_LONG), what(e.kind), isNum(e.distance_km) ? num(e.distance_km, 1) + " km" : "–", isNum(e.dur_min) ? String(e.dur_min) : "–", isNum(e.pace_min_km) ? paceFmt(e.pace_min_km) : "–", isNum(e.avg_hr) ? String(e.avg_hr) : "–"]; }) }; }
    });
    var tests = TR.tests || {}, tkeys = Object.keys(tests);
    if (tkeys.length) g = section(root, T.tests, null);
    tkeys.forEach(function (m) {
      var pts = tests[m], unit = (pts[pts.length - 1] || {}).unit || "";
      var pmap = { points: pts.filter(function (p) { return keys.indexOf(p.day) >= 0; }), latest: pts[pts.length - 1], previous: pts[pts.length - 2] };
      measureCard(g, D, pmap, pretty(m), unit, 0);
    });

    g = section(root, null, null);
    var ng = TR.next_goals || [];
    addCard(g, { title: T.next_goals, sub: T.next_goals_sub, empty: !ng.length, emptyText: T.goals_hint, custom: function (card) {
      var wrap = el("div", "table-wrap static");
      wrap.appendChild(buildTable({
        head: [T.exercise, T.plan, T.sets_reps, T.working, T.next_kg, T.last_logged], num: [3, 4],
        rows: ng.map(function (x) {
          var nk = isNum(x.next_kg) && isNum(x.kg) && x.next_kg > x.kg ? chip("good", num1(x.next_kg) + " kg", "↑") : isNum(x.next_kg) ? num1(x.next_kg) + " kg" : "–";
          return [pretty(x.name), x.plan || "–", (x.sets || "–") + " × " + (x.reps || "–"), isNum(x.kg) ? num1(x.kg) + " kg" : "–", nk,
            x.last_day ? num1(x.last_kg) + " kg × " + (x.last_reps || "–") + " · " + fmtDay(x.last_day, DAY_SHORT) : "–"];
        })
      }));
      card.appendChild(wrap);
    } }, "full");
  }

  // ------------------------------------------------------------------------------------------
  // tab: journal
  // ------------------------------------------------------------------------------------------

  function tabJournal(root, D) {
    var J = D.tabs.journal, reviews = J.reviews || [];
    var g = section(root, null, null, "grid-journal");
    addCard(g, { title: T.reviews, sub: T.reviews_sub, empty: !reviews.length, emptyText: T.reviews_none, hint: T.reviews_hint, cls: "reviews-card", custom: function (card) {
      var layout = el("div", "reviews");
      var nav = el("div", "review-list");
      nav.setAttribute("role", "listbox");
      nav.setAttribute("aria-label", T.reviews);
      var view = el("div", "md review-view");
      view.setAttribute("aria-live", "polite");
      var pick = function (file) {
        state.review = file;
        nav.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-selected", String(b.getAttribute("data-file") === file)); });
        view.textContent = "…";
        fetch("api/review?file=" + encodeURIComponent(file), { cache: "no-store" }).then(function (r) {
          return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; });
        }).then(function (j) {
          if (state.review !== file) return;
          view.innerHTML = window.BosMarkdown.render(j.text);
        }).catch(function (e) { view.textContent = T.load_error + ": " + (e.message || e); });
      };
      reviews.forEach(function (r) {
        var b = el("button", "review-item");
        b.type = "button";
        b.setAttribute("role", "option");
        b.setAttribute("data-file", r.file);
        b.appendChild(el("span", "review-title", r.title));
        b.appendChild(el("span", "review-meta", r.file.replace(/\.md$/, "") + " · " + (r.kind === "weekly" ? T.weekly : T.monthly)));
        b.addEventListener("click", function () { pick(r.file); });
        nav.appendChild(b);
      });
      layout.appendChild(nav);
      layout.appendChild(view);
      card.appendChild(layout);
      var want = reviews.some(function (r) { return r.file === state.review; }) ? state.review : reviews[0].file;
      pick(want);
    } }, "wide");
    var dec = J.decisions || [];
    addCard(g, { title: T.decisions, sub: T.decisions_sub, empty: !dec.length, emptyText: T.decisions_hint, custom: function (card) {
      var ul = el("ul", "rows decisions");
      dec.slice().sort(function (a, b) { return (a.status === "open" ? 0 : 1) - (b.status === "open" ? 0 : 1) || String(a.date).localeCompare(String(b.date)); }).forEach(function (d) {
        var li = el("li", "row");
        li.appendChild(chip(d.status === "done" ? "good" : d.days_left != null && d.days_left < 0 ? "warning" : "neutral", d.status === "done" ? T.done : d.days_left != null && d.days_left < 0 ? T.overdue : T.open));
        var t = el("div", "row-label");
        t.appendChild(el("div", "decision-title", d.title));
        var meta = [];
        if (d.date) meta.push(fmtDay(d.date, DAY_LONG) + (d.status === "open" ? " · " + relDay(d.date, D.today) : ""));
        if (d.note) meta.push(d.note);
        if (meta.length) t.appendChild(el("div", "decision-note", meta.join(" · ")));
        li.appendChild(t);
        ul.appendChild(li);
      });
      card.appendChild(ul);
    } });
    g = section(root, null, null);
    var tl = J.timeline || [];
    addCard(g, { title: T.timeline_j, sub: T.timeline_j_sub, empty: !tl.length, emptyText: T.empty_period, custom: function (card) {
      var ol = el("ol", "timeline");
      var lastDay = null;
      tl.forEach(function (n) {
        if (n.day !== lastDay) { ol.appendChild(el("li", "tl-day", fmtDay(n.day, { weekday: "long", day: "numeric", month: "long" }))); lastDay = n.day; }
        var li = el("li", "tl-item");
        li.appendChild(el("span", "tl-time", n.time));
        var body = el("div", "tl-body");
        var head = el("div", "tl-head");
        head.appendChild(el("span", "tl-type", (T.type[n.type] || n.type) + (n.field === "note" ? " · " + T.type.note : "")));
        if (isNum(n.severity)) head.appendChild(el("span", "tl-tag", tpl(T.severity, { n: n.severity })));
        (n.tags || []).forEach(function (t) { head.appendChild(el("span", "tl-tag", "#" + t)); });
        body.appendChild(head);
        body.appendChild(el("div", "tl-text", n.text));
        li.appendChild(body);
        ol.appendChild(li);
      });
      card.appendChild(ol);
    } }, "full");
  }

  // ------------------------------------------------------------------------------------------
  // tabs, routing, page
  // ------------------------------------------------------------------------------------------

  var BUILDERS = { today: tabToday, body: tabBody, nutrition: tabNutrition, kitchen: tabKitchen, sleep: tabSleep,
    substances: tabSubstances, training: tabTraining, journal: tabJournal };

  function lang() { return T === I18N.de ? "de" : "en"; }
  function slugFor(id) { var t = TABS.filter(function (x) { return x.id === id; })[0]; return lang() === "de" ? t.de : t.id; }

  function tabFromHash() {
    var h = decodeURIComponent((location.hash || "").replace(/^#\/?/, "")).toLowerCase();
    return ALIAS[h] || "today";
  }

  function buildTabBar() {
    var nav = document.getElementById("tabs");
    nav.innerHTML = "";
    nav.setAttribute("aria-label", T.tabs_label);
    TABS.forEach(function (t) {
      var a = el("a", "tab");
      a.href = "#" + slugFor(t.id);
      a.id = "tab-" + t.id;
      a.setAttribute("role", "tab");
      a.setAttribute("aria-controls", "panel-" + t.id);
      a.appendChild(el("span", null, T.tab[t.id]));
      if (t.id === "kitchen" && state.data) {
        var c = state.data.tabs.today.pantry_alerts.counts, n = (c.discard || 0) + (c.check || 0);
        if (n) { var b = el("span", "badge", String(n)); b.setAttribute("aria-label", n + " × " + T.status_check + "/" + T.status_discard); a.appendChild(b); }
      }
      nav.appendChild(a);
    });
  }

  function panelFor(id) {
    var p = state.panels[id];
    if (!p) {
      var sec = el("section", "panel");
      sec.id = "panel-" + id;
      sec.setAttribute("role", "tabpanel");
      sec.setAttribute("aria-labelledby", "tab-" + id);
      sec.hidden = true;
      document.getElementById("panels").appendChild(sec);
      p = state.panels[id] = { el: sec, built: false, charts: [], themeVer: -1 };
    }
    return p;
  }

  function disposePanels() {
    Object.keys(state.panels).forEach(function (k) {
      var p = state.panels[k];
      p.charts.forEach(function (c) { if (c.inst) c.inst.dispose(); });
      p.charts = [];
      p.built = false;
      p.el.innerHTML = "";
    });
  }

  function buildPanel(id, p) {
    var D = state.data;
    p.el.innerHTML = "";
    var q = el("p", "question", T.q[id]);
    p.el.appendChild(q);
    if (!D.period.days_logged && id !== "journal" && id !== "kitchen") {
      var bn = el("div", "banner");
      bn.appendChild(el("b", null, T.no_entries));
      bn.appendChild(el("span", null, T.no_entries_hint));
      p.el.appendChild(bn);
    }
    building = p;
    try { BUILDERS[id](p.el, D); } finally { building = null; }
    p.built = true;
  }

  function showTab(id, scroll) {
    state.tab = id;
    TABS.forEach(function (t) {
      var a = document.getElementById("tab-" + t.id);
      if (a) {
        a.setAttribute("aria-selected", String(t.id === id));
        a.tabIndex = t.id === id ? 0 : -1;
        if (t.id === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      }
    });
    var active = document.getElementById("tab-" + id), bar = document.getElementById("tabs");
    if (active && bar.scrollWidth > bar.clientWidth) {
      var left = active.offsetLeft - (bar.clientWidth - active.offsetWidth) / 2;
      try { bar.scrollTo({ left: left, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); } catch (e) { bar.scrollLeft = left; }
    }
    if (!state.data) return;
    document.title = T.tab[id] + " · body-os";
    Object.keys(state.panels).forEach(function (k) { state.panels[k].el.hidden = k !== id; });
    var p = panelFor(id);
    p.el.hidden = false;
    if (!p.built) {
      buildPanel(id, p);
      requestAnimationFrame(function () { renderPanelCharts(p); });
    } else if (p.themeVer !== state.themeVer) {
      requestAnimationFrame(function () { renderPanelCharts(p); });
    } else {
      requestAnimationFrame(function () { resizePanelCharts(p); });
    }
    if (scroll) window.scrollTo(0, 0);
  }

  function render(D) {
    T = I18N[(D.language || "en").slice(0, 2)] || I18N.en;
    document.documentElement.lang = lang();
    applyStaticText();
    var p = D.period, now = new Date();
    document.getElementById("subtitle").textContent = fmtDay(p.from, DAY_SHORT) + " – " +
      fmtDay(p.to, { day: "numeric", month: "short", year: "numeric" }) + " · " + T.updated + " " + pad2(now.getHours()) + ":" + pad2(now.getMinutes());
    document.querySelectorAll(".period button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-days") === p.key)); });
    disposePanels();
    buildTabBar();
    var id = tabFromHash(), want = "#" + slugFor(id);
    if (location.hash && location.hash !== want && history.replaceState) history.replaceState(null, "", want);
    showTab(id);
    var foot = document.getElementById("foot");
    foot.innerHTML = "";
    [T.foot_live, T.foot_raw, T.foot_credit].forEach(function (s) { foot.appendChild(el("span", null, s)); });
  }

  function applyStaticText() {
    document.querySelectorAll(".period").forEach(function (g) {
      g.setAttribute("aria-label", T.period);
      g.querySelectorAll("button").forEach(function (b) { var d = b.getAttribute("data-days"); b.textContent = d === "all" ? T.all : d + " " + T.days; });
    });
    document.getElementById("privacy-text").textContent = T.local_only + " · " + location.hostname;
    updateThemeButtons();
  }

  function showError(msg) {
    var root = document.getElementById("panels");
    disposePanels();
    var bn = document.getElementById("error") || el("div", "banner");
    bn.id = "error";
    bn.innerHTML = "";
    bn.appendChild(el("b", null, T.load_error));
    bn.appendChild(el("span", null, msg));
    root.parentNode.insertBefore(bn, root);
  }

  function load(period) {
    var url = "api/data" + (period ? "?days=" + encodeURIComponent(period) : "");
    state.loading = true;
    document.body.setAttribute("aria-busy", "true");
    return fetch(url, { cache: "no-store" }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; });
    }).then(function (D) {
      var err = document.getElementById("error");
      if (err) err.remove();
      state.data = D;
      state.period = D.period.key;
      render(D);
    }).catch(function (e) {
      showError(String(e.message || e));
    }).then(function () {
      state.loading = false;
      document.body.removeAttribute("aria-busy");
    });
  }

  // ------------------------------------------------------------------------------------------
  // theme
  // ------------------------------------------------------------------------------------------

  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function effectiveTheme() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t === "light" || t === "dark") return t;
    return mq && mq.matches ? "dark" : "light";
  }

  function updateThemeButtons() {
    var dark = effectiveTheme() === "dark";
    document.querySelectorAll(".theme-btn").forEach(function (b) {
      b.innerHTML = dark
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>';
      b.setAttribute("aria-label", dark ? T.theme_light : T.theme_dark);
      b.title = b.getAttribute("aria-label");
    });
  }

  function themeChanged() {
    state.themeVer++;
    updateThemeButtons();
    var p = state.panels[state.tab];
    if (p && p.built) renderPanelCharts(p);
  }

  // ------------------------------------------------------------------------------------------
  // wiring
  // ------------------------------------------------------------------------------------------

  document.querySelectorAll(".theme-btn").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = effectiveTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", t);
      store("bos-theme", t);
      themeChanged();
    });
  });
  if (mq) {
    if (mq.addEventListener) mq.addEventListener("change", themeChanged); else if (mq.addListener) mq.addListener(themeChanged);
  }
  document.querySelectorAll(".period").forEach(function (g) {
    g.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b || state.loading) return;
      var d = b.getAttribute("data-days");
      store("bos-period", d);
      load(d);
    });
  });
  window.addEventListener("hashchange", function () { showTab(tabFromHash(), true); });
  document.getElementById("tabs").addEventListener("keydown", function (e) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    var i = TABS.map(function (t) { return t.id; }).indexOf(state.tab);
    var n = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
    location.hash = slugFor(n.id);
    var a = document.getElementById("tab-" + n.id);
    if (a) a.focus();
    e.preventDefault();
  });

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () { var p = state.panels[state.tab]; if (p && p.built) resizePanelCharts(p); }, 120);
  });

  state.tab = tabFromHash();
  updateThemeButtons();
  var saved = store("bos-period");
  load(saved === "14" || saved === "30" || saved === "90" || saved === "all" ? saved : null);
})();
