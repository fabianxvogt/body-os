/* body-os dashboard — vanilla JS, no build step, no external requests.
 * Data: GET /api/data?days=14|30|90|all, rebuilt live from me/ on every request (see tools/bos.py
 * dashboard_data). Charts: Apache ECharts (vendor/, Apache-2.0). Colours come from CSS custom
 * properties in style.css so light/dark stay one system; charts re-render on theme change. */
(function () {
  "use strict";

  // ------------------------------------------------------------------------------------------
  // i18n
  // ------------------------------------------------------------------------------------------

  var I18N = {
    en: {
      locale: "en-GB", days: "days", all: "All", period: "Period", updated: "updated",
      local_only: "local only", theme_dark: "Switch to dark theme", theme_light: "Switch to light theme",
      table: "Table", chart: "Chart", empty: "No data yet – arrives with your first check-in",
      load_error: "Could not load data", no_entries: "No entries in this period yet.",
      no_entries_hint: "Log a check-in with your agent and reload this page.",
      day: "Day", week: "Week", wk: "W", total: "Total", none: "none", more: "more", less: "less",
      sec_body: "Body", sec_body_sub: "weight and measurements",
      sec_food: "Nutrition & drinks", sec_food_sub: "per day, from logged meals and drinks",
      sec_sleep: "Sleep", sec_sleep_sub: "night counted for the morning you wake up",
      sec_use: "Substances", sec_use_sub: "counts and habit times",
      sec_mind: "Wellbeing & training", sec_mind_sub: "check-ins, sessions and strength",
      sec_kitchen: "Pantry & kitchen", sec_kitchen_sub: "what needs attention, what you cooked",
      kpi_weight: "Weight", kpi_weight_sub_delta: "vs. 7 days ago", kpi_weight_sub: "7-day mean",
      kpi_protein: "Protein Ø / day", kpi_protein_target: "target", kpi_protein_sub: "on days with meals",
      kpi_sleep: "Sleep Ø", kpi_sleep_q: "quality Ø",
      kpi_use: "Use / day", kpi_joint: "Joints / day", kpi_cigarette: "Cigarettes / day",
      kpi_tobacco: "with tobacco Ø", kpi_prev: "vs. previous", kpi_train: "Training this week",
      kpi_train_sub: "of {n} planned",
      weight: "Weight", weight_sub: "kg · daily weigh-in and 7-day mean", daily: "Daily", avg7: "7-day mean",
      protein: "Protein per day", protein_sub: "g · bars per day", target: "Target",
      kcal: "Calories per day", kcal_sub: "kcal · logged meals",
      water: "Water", water_sub: "litres per day", coffee: "Coffee", coffee_sub: "caffeinated drinks per day",
      last_coffee: "last",
      sleep: "Sleep", sleep_sub: "hours per night · line at 7 h", quality: "Quality", wakeups: "Wake-ups",
      hours: "Hours",
      svu: "Sleep vs. last use the evening before", svu_sub: "time of last use after 18:00 → hours slept",
      svu_use: "Use in the evening", svu_none: "No evening use", last_use: "Last use",
      no_use: "nothing after 18:00", svu_note: "{n} nights · patterns are hypotheses, not proof",
      trig: "Use per day by trigger", trig_sub: "count · stacked by trigger", other: "Other",
      tobacco: "with tobacco", last: "last",
      heat: "Use times", heat_sub: "weekday × hour · more intense = more often",
      weekdays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], uses: "×", hour: "Hour",
      mind: "Energy, mood, stress", mind_sub: "check-ins 1–5 · stress 5 = high",
      energy: "Energy", mood: "Mood", stress: "Stress",
      train: "Training sessions per week", train_sub: "sessions · dashed line = plan", plan: "Plan",
      sessions: "Sessions", minutes: "Minutes",
      lifts: "Strength", lifts_sub: "kg · top set per session", e1rm: "e1RM", others: "Also logged",
      waist: "Waist", waist_sub: "cm", bp: "Blood pressure", bp_sub: "mmHg · systolic and diastolic",
      sys: "Systolic", dia: "Diastolic", pulse: "Pulse", rhr: "Resting heart rate", rhr_sub: "bpm",
      pantry: "Pantry", pantry_sub: "most urgent first", item: "Item", left: "Left", storage: "Storage",
      expiry: "Expiry", status_discard: "discard", status_check: "check", status_soon: "soon", status_ok: "ok",
      days_left: "{n} d left", days_past: "{n} d past", today: "today", no_date: "no date", opened: "opened",
      est: "estimated", fridge: "fridge", freezer: "freezer", pantry_store: "pantry",
      cookbook: "Cookbook", cookbook_sub: "last cooked and suggested", simplicity: "Simplicity",
      nutrition: "Nutrition", rating: "Rating", suggested: "suggested", cooked: "cooked",
      foot_live: "Live from me/ on every reload · nothing leaves this machine",
      foot_raw: "Raw tables: bos dash", foot_credit: "Charts: Apache ECharts 5.5.1 (Apache-2.0)",
      triggers: { "?": "unknown", "after-meal": "after meal" }
    },
    de: {
      locale: "de-DE", days: "Tage", all: "Alles", period: "Zeitraum", updated: "aktualisiert",
      local_only: "nur lokal", theme_dark: "Dunkles Design", theme_light: "Helles Design",
      table: "Tabelle", chart: "Diagramm", empty: "Noch keine Daten – kommt mit deinem ersten Check-in",
      load_error: "Daten konnten nicht geladen werden", no_entries: "Noch keine Einträge in diesem Zeitraum.",
      no_entries_hint: "Mach einen Check-in mit deinem Agenten und lade die Seite neu.",
      day: "Tag", week: "Woche", wk: "KW ", total: "Gesamt", none: "keiner", more: "mehr", less: "weniger",
      sec_body: "Körper", sec_body_sub: "Gewicht und Maße",
      sec_food: "Ernährung & Trinken", sec_food_sub: "pro Tag, aus geloggten Mahlzeiten und Getränken",
      sec_sleep: "Schlaf", sec_sleep_sub: "Nacht zählt für den Morgen, an dem du aufwachst",
      sec_use: "Konsum", sec_use_sub: "Mengen und Gewohnheitszeiten",
      sec_mind: "Befinden & Training", sec_mind_sub: "Check-ins, Einheiten und Kraftwerte",
      sec_kitchen: "Vorrat & Küche", sec_kitchen_sub: "was Aufmerksamkeit braucht, was du gekocht hast",
      kpi_weight: "Gewicht", kpi_weight_sub_delta: "vs. vor 7 Tagen", kpi_weight_sub: "7-Tage-Schnitt",
      kpi_protein: "Protein Ø / Tag", kpi_protein_target: "Ziel", kpi_protein_sub: "an Tagen mit Mahlzeiten",
      kpi_sleep: "Schlaf Ø", kpi_sleep_q: "Qualität Ø",
      kpi_use: "Konsum / Tag", kpi_joint: "Joints / Tag", kpi_cigarette: "Zigaretten / Tag",
      kpi_tobacco: "davon mit Tabak Ø", kpi_prev: "vs. Vorperiode", kpi_train: "Training diese Woche",
      kpi_train_sub: "von {n} geplant",
      weight: "Gewicht", weight_sub: "kg · tägliche Messung und 7-Tage-Schnitt", daily: "Tageswert",
      avg7: "7-Tage-Schnitt",
      protein: "Protein pro Tag", protein_sub: "g · Balken pro Tag", target: "Ziel",
      kcal: "Kalorien pro Tag", kcal_sub: "kcal · geloggte Mahlzeiten",
      water: "Wasser", water_sub: "Liter pro Tag", coffee: "Kaffee", coffee_sub: "koffeinhaltige Getränke pro Tag",
      last_coffee: "zuletzt",
      sleep: "Schlaf", sleep_sub: "Stunden pro Nacht · Linie bei 7 h", quality: "Qualität", wakeups: "Wachphasen",
      hours: "Stunden",
      svu: "Schlaf vs. letzter Konsum am Vorabend", svu_sub: "Uhrzeit des letzten Konsums nach 18 Uhr → Schlafdauer",
      svu_use: "Konsum am Abend", svu_none: "Kein Konsum am Abend", last_use: "Letzter Konsum",
      no_use: "nichts nach 18 Uhr", svu_note: "{n} Nächte · Muster sind Hypothesen, kein Beweis",
      trig: "Konsum pro Tag nach Auslöser", trig_sub: "Anzahl · gestapelt nach Auslöser", other: "Sonstiges",
      tobacco: "mit Tabak", last: "zuletzt",
      heat: "Konsum-Uhrzeiten", heat_sub: "Wochentag × Stunde · intensiver = häufiger",
      weekdays: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], uses: "×", hour: "Stunde",
      mind: "Energie, Stimmung, Stress", mind_sub: "Check-ins 1–5 · Stress 5 = hoch",
      energy: "Energie", mood: "Stimmung", stress: "Stress",
      train: "Trainingseinheiten pro Woche", train_sub: "Einheiten · gestrichelt = Plan", plan: "Plan",
      sessions: "Einheiten", minutes: "Minuten",
      lifts: "Kraftwerte", lifts_sub: "kg · schwerster Satz pro Einheit", e1rm: "e1RM", others: "Außerdem geloggt",
      waist: "Bauchumfang", waist_sub: "cm", bp: "Blutdruck", bp_sub: "mmHg · systolisch und diastolisch",
      sys: "Systolisch", dia: "Diastolisch", pulse: "Puls", rhr: "Ruhepuls", rhr_sub: "Schläge/min",
      pantry: "Bestand", pantry_sub: "dringendstes zuerst", item: "Artikel", left: "Rest", storage: "Lagerort",
      expiry: "Haltbarkeit", status_discard: "wegwerfen", status_check: "prüfen", status_soon: "bald", status_ok: "ok",
      days_left: "noch {n} T.", days_past: "{n} T. drüber", today: "heute", no_date: "ohne Datum",
      opened: "offen", est: "geschätzt", fridge: "Kühlschrank", freezer: "Gefrierfach", pantry_store: "Vorrat",
      cookbook: "Kochbuch", cookbook_sub: "zuletzt gekocht und vorgeschlagen", simplicity: "Einfachheit",
      nutrition: "Nährwert", rating: "Bewertung", suggested: "vorgeschlagen", cooked: "gekocht",
      foot_live: "Live aus me/ bei jedem Neuladen · nichts verlässt diesen Rechner",
      foot_raw: "Rohdaten-Tabellen: bos dash", foot_credit: "Charts: Apache ECharts 5.5.1 (Apache-2.0)",
      triggers: {
        "?": "unbekannt", stress: "Stress", boredom: "Langeweile", "after-meal": "nach dem Essen",
        "break": "Pause", evening: "Abend", social: "sozial", habit: "Gewohnheit", craving: "Verlangen"
      }
    }
  };

  var T = I18N.en;
  var STATUS_ICON = { discard: "⛔", check: "🔍", soon: "⏳", ok: "✓" };
  var LINE_ICON = "path://M0,4.5 L20,4.5 L20,7.5 L0,7.5 Z";

  var state = { period: null, data: null, charts: [], loading: false };

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
    return s.replace(/\{(\w+)\}/g, function (_, k) { return vars[k]; });
  }

  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function num(v, nd) {
    if (!isNum(v)) return "–";
    nd = nd || 0;
    return new Intl.NumberFormat(T.locale, { minimumFractionDigits: nd, maximumFractionDigits: nd }).format(v);
  }

  function signed(v, nd) {
    if (!isNum(v)) return "–";
    var s = num(Math.abs(v), nd);
    return (v > 0 ? "+" : v < 0 ? "−" : "±") + s;
  }

  function mean(xs) {
    var v = xs.filter(isNum);
    return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null;
  }

  function parseDay(s) {
    var p = s.split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }

  function fmtDay(s, opts) {
    return new Intl.DateTimeFormat(T.locale, opts).format(parseDay(s));
  }
  var DAY_SHORT = { day: "numeric", month: "short" };
  var DAY_AXIS = { day: "numeric", month: "numeric" };
  var DAY_LONG = { weekday: "short", day: "numeric", month: "short" };

  function hm(h) {
    if (!isNum(h)) return "–";
    var m = Math.round(h * 60);
    return Math.floor(m / 60) + " h " + (m % 60 < 10 ? "0" : "") + (m % 60) + " min";
  }

  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var day = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - day);
    var y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil(((t - y0) / 86400000 + 1) / 7);
  }

  function trig(name) {
    return (T.triggers && T.triggers[name]) || I18N.en.triggers[name] || name;
  }

  function pal() {
    var cs = getComputedStyle(document.documentElement);
    var g = function (n) { return cs.getPropertyValue(n).trim(); };
    var i, c = [], s = [];
    for (i = 1; i <= 8; i++) c.push(g("--c" + i));
    for (i = 1; i <= 7; i++) s.push(g("--s" + i));
    return {
      c: c, seq: s, other: g("--other"), text: g("--text"), text2: g("--text-2"), muted: g("--muted"),
      grid: g("--grid"), axis: g("--axis"), surface: g("--surface"), raised: g("--raised"),
      border: g("--border"), hover: g("--hover"), cell: g("--cell"), band: g("--band"), font: g("--font")
    };
  }

  // ------------------------------------------------------------------------------------------
  // chart building blocks (thin marks, recessive axes, text in text colours)
  // ------------------------------------------------------------------------------------------

  function grid(o) {
    return Object.assign({ left: 2, right: 14, top: 14, bottom: 2, containLabel: true }, o || {});
  }

  function xDays(P, keys, w) {
    return {
      type: "category", data: keys, boundaryGap: true,
      axisLine: { lineStyle: { color: P.axis } }, axisTick: { show: false },
      axisLabel: {
        color: P.text2, fontSize: 11, hideOverlap: true, margin: 10,
        formatter: function (v) { return fmtDay(v, DAY_AXIS); }
      },
      axisPointer: { label: { show: false } }
    };
  }

  function yVal(P, o) {
    o = o || {};
    var y = Object.assign({
      type: "value", splitNumber: 4,
      splitLine: { lineStyle: { color: P.grid } },
      axisLine: { show: false }, axisTick: { show: false }
    }, o);
    y.axisLabel = Object.assign({ color: P.text2, fontSize: 11 }, o.axisLabel || {});
    return y;
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
      t.axisPointer = pointer === "shadow"
        ? { type: "shadow", shadowStyle: { color: P.hover } }
        : { type: "line", lineStyle: { color: P.axis, width: 1 } };
    }
    return t;
  }

  // rows: [{color, label, value}] (label/value already formatted; label is escaped here)
  function tipHtml(title, rows, foot) {
    var h = '<div class="tt-title">' + esc(title) + "</div>";
    rows.forEach(function (r) {
      h += '<div class="tt-row">' + (r.color ? '<span class="tt-dot" style="background:' + r.color + '"></span>' : "") +
        '<span class="tt-label">' + esc(r.label) + '</span><span class="tt-val">' + esc(r.value) + "</span></div>";
    });
    if (foot) h += '<div class="tt-foot">' + esc(foot) + "</div>";
    return h;
  }

  function bar(name, data, color, o) {
    return Object.assign({
      name: name, type: "bar", data: data, barMaxWidth: 16, barCategoryGap: "28%",
      itemStyle: { color: color, borderRadius: [4, 4, 0, 0] },
      emphasis: { itemStyle: { color: color } }
    }, o || {});
  }

  function line(name, data, color, o) {
    return Object.assign({
      name: name, type: "line", data: data, connectNulls: true, smooth: 0.2,
      symbol: "circle", symbolSize: 7, showSymbol: data.filter(function (v) { return v != null; }).length <= 40,
      lineStyle: { width: 2, color: color }, itemStyle: { color: color },
      emphasis: { focus: "series", scale: 1.3 }
    }, o || {});
  }

  function refLine(P, value, label) {
    return {
      silent: true, symbol: "none", animation: false,
      lineStyle: { color: P.text2, type: [4, 4], width: 1, opacity: 0.8 },
      label: { show: !!label, formatter: label, position: "end", distance: 4, color: P.text2, fontSize: 11 },
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

  // Value axis with a little headroom around the data (sparse series would otherwise look extreme).
  function pad(minPad) {
    // headroom of max(minPad, 15 % of the range), then let ECharts pick nice ticks via boundaryGap
    return {
      scale: true,
      min: function (v) { return v.min - Math.max(minPad, (v.max - v.min) * 0.15); },
      max: function (v) { return v.max + Math.max(minPad, (v.max - v.min) * 0.15); },
      axisLabel: { showMinLabel: false, showMaxLabel: false }
    };
  }

  function has(rows, key) {
    return rows.some(function (r) { return isNum(r[key]); });
  }

  function dayTable(days, cols) {
    // cols: [{label, get(row) -> string|null, num}] — rows without any value are skipped
    var rows = [];
    days.forEach(function (d) {
      var vals = cols.map(function (c) { return c.get(d); });
      if (vals.some(function (v) { return v != null && v !== "–"; })) rows.push([fmtDay(d.day, DAY_LONG)].concat(vals));
    });
    return {
      head: [T.day].concat(cols.map(function (c) { return c.label; })),
      num: cols.map(function (c, i) { return c.num ? i + 1 : -1; }), rows: rows
    };
  }

  // ------------------------------------------------------------------------------------------
  // chart specs: each returns {title, sub, empty, option(P, w), table, note, cls}
  // ------------------------------------------------------------------------------------------

  function specs(D) {
    var days = D.days, keys = days.map(function (d) { return d.day; });
    var col = function (k) { return days.map(function (d) { return isNum(d[k]) ? d[k] : null; }); };
    var targets = D.targets || {};
    var out = {};

    function target(key) {
      var t = targets[key];
      if (isNum(t)) return { lo: t, hi: null };
      if (Array.isArray(t) && isNum(t[0])) return { lo: t[0], hi: isNum(t[1]) ? t[1] : null };
      if (isNum(targets[key + "_min"])) return { lo: targets[key + "_min"], hi: isNum(targets[key + "_max"]) ? targets[key + "_max"] : null };
      return null;
    }

    function dayAxisTip(P, rowsFor, pointer) {
      return tooltip(P, "axis", pointer || "line", function (ps) {
        var i = ps[0].dataIndex, d = days[i];
        return tipHtml(fmtDay(d.day, DAY_LONG), rowsFor(d, i));
      });
    }
    function barTip(P, rowsFor) { return dayAxisTip(P, rowsFor, "shadow"); }

    // ---- weight
    out.weight = {
      title: T.weight, sub: T.weight_sub, empty: !has(days, "weight_kg"),
      option: function (P) {
        return {
          grid: grid({ top: 36, right: 58 }), legend: legend(P, [{ name: T.daily, icon: "circle" }, { name: T.avg7, icon: LINE_ICON }]),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var d = days[ps[0].dataIndex];
            return tipHtml(fmtDay(d.day, DAY_LONG), [
              { color: P.c[0], label: T.daily, value: isNum(d.weight_kg) ? num(d.weight_kg, 1) + " kg" : "–" },
              { color: P.c[0], label: T.avg7, value: isNum(d.weight_7d) ? num(d.weight_7d, 1) + " kg" : "–" }]);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(1)),
          series: [
            { name: T.daily, type: "scatter", data: col("weight_kg"), symbolSize: 8, z: 3,
              itemStyle: { color: P.c[0], opacity: 0.45, borderColor: P.surface, borderWidth: 1.5 } },
            line(T.avg7, lastLabel(col("weight_7d"), {
              color: P.text, fontWeight: 600, fontSize: 12, formatter: function (p) { return num(p.value, 1) + " kg"; }
            }), P.c[0], { showSymbol: true, symbolSize: 0, z: 4 })
          ]
        };
      },
      table: function () {
        return dayTable(days, [
          { label: T.daily + " (kg)", num: true, get: function (d) { return isNum(d.weight_kg) ? num(d.weight_kg, 1) : null; } },
          { label: T.avg7 + " (kg)", num: true, get: function (d) { return isNum(d.weight_kg) ? num(d.weight_7d, 2) : null; } }]);
      }
    };

    // ---- protein (target band) and calories
    var pt = target("protein_g");
    out.protein = {
      title: T.protein, sub: T.protein_sub + (pt ? " · " + T.target + " " + num(pt.lo) + (pt.hi ? "–" + num(pt.hi) : "+") + " g" : ""),
      empty: !has(days, "protein_g"),
      option: function (P) {
        var vals = col("protein_g"), mx = Math.max.apply(null, vals.filter(isNum).concat([0]));
        var top = pt ? Math.ceil(Math.max(mx, (pt.hi || pt.lo * 1.2)) / 20) * 20 : null;
        var s = bar(T.protein, vals, P.c[2]);
        if (pt) {
          s.markArea = { silent: true, animation: false, itemStyle: { color: P.band },
            data: [[{ yAxis: pt.lo }, { yAxis: pt.hi || top }]] };
          s.markLine = refLine(P, pt.lo, T.target + " " + num(pt.lo) + " g");
          s.markLine.label.position = "insideStartTop";
          s.markLine.label.distance = 3;
        }
        return {
          grid: grid({ top: 16 }),
          tooltip: barTip(P, function (d) {
            var r = [{ color: P.c[2], label: T.protein, value: isNum(d.protein_g) ? num(d.protein_g) + " g" : "–" }];
            if (pt && isNum(d.protein_g)) r.push({ label: T.target, value: Math.round(d.protein_g / pt.lo * 100) + " %" });
            return r;
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, top ? { max: top } : {}), series: [s]
        };
      },
      table: function () {
        return dayTable(days, [{ label: T.protein + " (g)", num: true, get: function (d) { return isNum(d.protein_g) ? num(d.protein_g) : null; } }]);
      }
    };

    var kt = target("kcal");
    out.kcal = {
      title: T.kcal, sub: T.kcal_sub, empty: !has(days, "kcal"),
      option: function (P) {
        var s = bar(T.kcal, col("kcal"), P.c[1]);
        if (kt) s.markLine = refLine(P, kt.lo, T.target + " " + num(kt.lo));
        return {
          grid: grid({ top: 16, right: kt ? 84 : 14 }),
          tooltip: barTip(P, function (d) { return [{ color: P.c[1], label: T.kcal, value: isNum(d.kcal) ? num(d.kcal) + " kcal" : "–" }]; }),
          xAxis: xDays(P, keys), yAxis: yVal(P), series: [s]
        };
      },
      table: function () {
        return dayTable(days, [{ label: "kcal", num: true, get: function (d) { return isNum(d.kcal) ? num(d.kcal) : null; } }]);
      }
    };

    // ---- drinks
    var water = days.map(function (d) { return d.logged && d.water_ml > 0 ? d.water_ml / 1000 : null; });
    out.water = {
      title: T.water, sub: T.water_sub, empty: !water.some(isNum),
      option: function (P) {
        return {
          grid: grid({ top: 16 }),
          tooltip: barTip(P, function (d, i) { return [{ color: P.c[0], label: T.water, value: isNum(water[i]) ? num(water[i], 2) + " L" : "–" }]; }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { axisLabel: { color: P.text2, fontSize: 11, formatter: function (v) { return num(v, 1); } } }),
          series: [bar(T.water, water, P.c[0])]
        };
      },
      table: function () {
        return dayTable(days, [{ label: T.water + " (L)", num: true, get: function (d) { return d.logged && d.water_ml > 0 ? num(d.water_ml / 1000, 2) : null; } }]);
      }
    };

    var coffee = days.map(function (d) { return d.logged ? d.caffeine_n : null; });
    out.coffee = {
      title: T.coffee, sub: T.coffee_sub, empty: !days.some(function (d) { return d.caffeine_n > 0; }),
      option: function (P) {
        return {
          grid: grid({ top: 16 }),
          tooltip: barTip(P, function (d) {
            var r = [{ color: P.c[3], label: T.coffee, value: d.logged ? num(d.caffeine_n) : "–" }];
            if (d.last_caffeine) r.push({ label: T.last_coffee, value: d.last_caffeine });
            return r;
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { minInterval: 1 }),
          series: [bar(T.coffee, coffee, P.c[3])]
        };
      },
      table: function () {
        return dayTable(days, [
          { label: T.coffee, num: true, get: function (d) { return d.logged ? String(d.caffeine_n) : null; } },
          { label: T.last_coffee, get: function (d) { return d.last_caffeine || null; } }]);
      }
    };

    // ---- sleep
    out.sleep = {
      title: T.sleep, sub: T.sleep_sub, empty: !has(days, "sleep_h"),
      option: function (P) {
        var s = bar(T.sleep, col("sleep_h"), P.c[6]);
        s.markLine = refLine(P, 7, "7 h");
        return {
          grid: grid({ top: 16, right: 36 }),
          tooltip: barTip(P, function (d) {
            return [{ color: P.c[6], label: T.sleep, value: hm(d.sleep_h) },
              { label: T.quality, value: isNum(d.sleep_quality) ? num(d.sleep_quality, d.sleep_quality % 1 ? 1 : 0) + " / 5" : "–" },
              { label: T.wakeups, value: isNum(d.wakeups) ? String(d.wakeups) : "–" }];
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { min: 0, interval: 2, max: function (v) { return Math.max(10, Math.ceil(v.max / 2) * 2); } }),
          series: [s]
        };
      },
      table: function () {
        return dayTable(days, [
          { label: T.hours, num: true, get: function (d) { return isNum(d.sleep_h) ? num(d.sleep_h, 1) : null; } },
          { label: T.quality, num: true, get: function (d) { return isNum(d.sleep_quality) ? num(d.sleep_quality, 1) : null; } },
          { label: T.wakeups, num: true, get: function (d) { return isNum(d.wakeups) ? String(d.wakeups) : null; } }]);
      }
    };

    // ---- sleep vs. last use the evening before
    var svu = D.sleep_vs_last_use || [];
    out.svu = {
      title: T.svu, sub: T.svu_sub, empty: !svu.length || !svu.some(function (r) { return r.last_use_prev_evening; }),
      note: tpl(T.svu_note, { n: svu.length }),
      option: function (P, w) {
        var seen = {};
        var pt = function (r) {
          var x = r.minutes_after_18 == null ? -60 : r.minutes_after_18;
          var k = x + "|" + r.sleep_h, n = seen[k] = (seen[k] || 0) + 1;
          var jitter = n === 1 ? 0 : (n % 2 ? -1 : 1) * Math.ceil((n - 1) / 2) * 9;
          return { value: [x + jitter, r.sleep_h], r: r };
        };
        var use = svu.filter(function (r) { return r.minutes_after_18 != null; }).map(pt);
        var none = svu.filter(function (r) { return r.minutes_after_18 == null; }).map(pt);
        var dot = function (c) { return { color: c, borderColor: P.surface, borderWidth: 1.5 }; };
        return {
          grid: grid({ top: 36, right: 18 }),
          legend: legend(P, [{ name: T.svu_use, icon: "circle" }, { name: T.svu_none, icon: "circle" }]),
          tooltip: tooltip(P, "item", null, function (p) {
            var r = p.data.r;
            return tipHtml(fmtDay(r.day, DAY_LONG), [
              { color: p.color, label: T.last_use, value: r.last_use_prev_evening || T.no_use },
              { label: T.sleep, value: hm(r.sleep_h) },
              { label: T.quality, value: isNum(r.quality) ? num(r.quality, r.quality % 1 ? 1 : 0) + " / 5" : "–" }]);
          }),
          xAxis: {
            type: "value", min: -90, max: 540, interval: 30,
            axisLine: { show: true, lineStyle: { color: P.axis } }, axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: {
              color: P.text2, fontSize: 11, margin: 10,
              formatter: function (v) {
                if (v === -60) return T.none;
                var step = w < 520 ? 180 : 120;
                if (v < 0 || v % step !== 0 || (w < 520 && v === 0)) return "";
                var h = (18 + v / 60) % 24;
                return (h < 10 ? "0" : "") + h + ":00";
              }
            }
          },
          yAxis: yVal(P, { scale: true, minInterval: 0.5, axisLabel: { color: P.text2, fontSize: 11, formatter: function (v) { return num(v, v % 1 ? 1 : 0) + " h"; } } }),
          series: [
            { name: T.svu_use, type: "scatter", data: use, symbolSize: 10, itemStyle: dot(P.c[0]),
              markLine: { silent: true, symbol: "none", animation: false, label: { show: false },
                lineStyle: { color: P.grid, type: "solid", width: 1 }, data: [{ xAxis: -25 }] } },
            { name: T.svu_none, type: "scatter", data: none, symbolSize: 10, itemStyle: dot(P.c[1]) }
          ]
        };
      },
      table: function () {
        return {
          head: [T.day, T.last_use, T.hours, T.quality], num: [-1, -1, 2, 3],
          rows: svu.map(function (r) {
            return [fmtDay(r.day, DAY_LONG), r.last_use_prev_evening || T.no_use, num(r.sleep_h, 1), isNum(r.quality) ? num(r.quality, 1) : "–"];
          })
        };
      }
    };

    // ---- use per day by trigger (stacked)
    var order = (D.trigger_order || []).slice(0, 6);
    var totals = D.triggers_total || {};
    var named = order.filter(function (t) { return totals[t]; });
    var otherSum = function (d) {
      var s = 0;
      Object.keys(d.triggers || {}).forEach(function (t) { if (order.indexOf(t) < 0) s += d.triggers[t]; });
      return s;
    };
    var hasOther = days.some(function (d) { return otherSum(d) > 0; });
    out.trig = {
      title: T.trig, sub: T.trig_sub, empty: !days.some(function (d) { return d.substance_n > 0; }),
      option: function (P) {
        var groups = named.map(function (t) {
          return { name: trig(t), color: P.c[order.indexOf(t)], get: function (d) { return (d.triggers || {})[t] || 0; } };
        });
        if (hasOther) groups.push({ name: T.other, color: P.other, get: otherSum });
        var topIdx = days.map(function (d) {
          var top = -1;
          groups.forEach(function (g, i) { if (g.get(d) > 0) top = i; });
          return top;
        });
        var series = groups.map(function (g, gi) {
          return {
            name: g.name, type: "bar", stack: "use", barMaxWidth: 16, barCategoryGap: "28%",
            itemStyle: { color: g.color, borderColor: P.surface, borderWidth: 1 },
            emphasis: { focus: "series" },
            data: days.map(function (d, i) {
              var v = d.logged ? g.get(d) : null;
              return topIdx[i] === gi ? { value: v, itemStyle: { borderRadius: [4, 4, 0, 0] } } : v;
            })
          };
        });
        return {
          grid: grid({ top: 38 }),
          legend: legend(P, groups.map(function (g) { return g.name; }), true),
          tooltip: tooltip(P, "axis", "shadow", function (ps) {
            var d = days[ps[0].dataIndex];
            var rows = ps.filter(function (p) { return p.value > 0 || (p.value && p.value.value > 0); }).reverse().map(function (p) {
              return { color: p.color, label: p.seriesName, value: String(isNum(p.value) ? p.value : p.value.value) };
            });
            rows.push({ label: T.total, value: String(d.substance_n) });
            var foot = d.substance_n ? T.tobacco + ": " + d.tobacco_n + (d.last_substance ? " · " + T.last + " " + d.last_substance : "") : null;
            return tipHtml(fmtDay(d.day, DAY_LONG), rows, foot);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { minInterval: 1 }), series: series
        };
      },
      table: function () {
        var cols = named.map(function (t) { return { label: trig(t), num: true, get: function (d) { return d.substance_n ? String((d.triggers || {})[t] || 0) : null; } }; });
        if (hasOther) cols.push({ label: T.other, num: true, get: function (d) { return d.substance_n ? String(otherSum(d)) : null; } });
        cols.push({ label: T.total, num: true, get: function (d) { return d.substance_n ? String(d.substance_n) : null; } });
        cols.push({ label: T.tobacco, num: true, get: function (d) { return d.substance_n ? String(d.tobacco_n) : null; } });
        return dayTable(days, cols);
      }
    };

    // ---- use times heatmap (weekday × hour, sequential blue)
    var ut = D.use_times || [];
    out.heat = {
      title: T.heat, sub: T.heat_sub, empty: !ut.length, cls: "tall",
      option: function (P, w) {
        var counts = {}, max = 1;
        ut.forEach(function (u) { counts[u.weekday + "|" + u.hour] = u.count; max = Math.max(max, u.count); });
        var zeros = [], vals = [];
        for (var wd = 0; wd < 7; wd++) for (var h = 0; h < 24; h++) {
          var c = counts[wd + "|" + h];
          (c ? vals : zeros).push([h, wd, c || 0]);
        }
        var cell = { borderColor: P.surface, borderWidth: w < 520 ? 1 : 2, borderRadius: 3 };
        return {
          grid: grid({ top: 6, bottom: 44, right: 4 }),
          tooltip: tooltip(P, "item", null, function (p) {
            var h = p.value[0];
            return tipHtml(T.weekdays[p.value[1]] + " · " + h + ":00–" + (h + 1) + ":00",
              [{ color: p.value[2] ? p.color : null, label: "", value: p.value[2] + T.uses }]);
          }),
          xAxis: {
            type: "category", data: Array.from({ length: 24 }, function (_, i) { return String(i); }),
            axisLine: { show: false }, axisTick: { show: false }, splitArea: { show: false },
            axisLabel: { color: P.text2, fontSize: 11, interval: w < 520 ? 5 : 2 }
          },
          yAxis: {
            type: "category", data: T.weekdays, inverse: true, axisLine: { show: false }, axisTick: { show: false },
            axisLabel: { color: P.text2, fontSize: 11 }
          },
          visualMap: {
            type: "continuous", seriesIndex: 1, min: 1, max: max, calculable: false, orient: "horizontal",
            right: 0, bottom: 0, itemWidth: 10, itemHeight: 120, text: [T.more, T.less],
            textGap: 8, textStyle: { color: P.text2, fontSize: 11 }, inRange: { color: P.seq.slice(1) }
          },
          series: [
            { type: "heatmap", data: zeros, itemStyle: Object.assign({ color: P.cell }, cell), emphasis: { disabled: true } },
            { type: "heatmap", data: vals, itemStyle: cell, emphasis: { itemStyle: { borderColor: P.text, borderWidth: 1 } } }
          ]
        };
      },
      table: function () {
        return {
          head: [T.day, T.hour, T.uses], num: [-1, 1, 2],
          rows: ut.slice().sort(function (a, b) { return b.count - a.count; }).map(function (u) {
            return [T.weekdays[u.weekday], u.hour + ":00", String(u.count)];
          })
        };
      }
    };

    // ---- energy / mood / stress
    var mindKeys = [["energy", T.energy], ["mood", T.mood], ["stress", T.stress]];
    out.mind = {
      title: T.mind, sub: T.mind_sub, empty: !mindKeys.some(function (k) { return has(days, k[0]); }),
      option: function (P, w) {
        var wide = w >= 520;
        return {
          grid: grid({ top: 36, right: wide ? 112 : 14 }),
          legend: legend(P, mindKeys.map(function (k) { return { name: k[1], icon: LINE_ICON }; })),
          tooltip: dayAxisTip(P, function (d) {
            return mindKeys.map(function (k, i) { return { color: P.c[i], label: k[1], value: isNum(d[k[0]]) ? num(d[k[0]], d[k[0]] % 1 ? 1 : 0) : "–" }; });
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, { min: 1, max: 5, interval: 1 }),
          series: (function () {
            // Lines ending on the same value share one end label ("Energy · Stress") instead of overlapping.
            var ends = mindKeys.map(function (k) {
              var c = col(k[0]);
              for (var j = c.length - 1; j >= 0; j--) if (isNum(c[j])) return j + ":" + c[j];
              return null;
            });
            return mindKeys.map(function (k, i) {
              var text = null;
              if (wide && ends[i] !== null && ends.indexOf(ends[i]) === i) {
                text = mindKeys.filter(function (_, j) { return ends[j] === ends[i]; })
                  .map(function (m) { return m[1]; }).join(" · ");
              }
              return line(k[1], text ? lastLabel(col(k[0]), { formatter: text, color: P.text2, fontSize: 11 }) : col(k[0]), P.c[i]);
            });
          })()
        };
      },
      table: function () {
        return dayTable(days, mindKeys.map(function (k) {
          return { label: k[1], num: true, get: function (d) { return isNum(d[k[0]]) ? num(d[k[0]], 1) : null; } };
        }));
      }
    };

    // ---- training per week vs plan
    var weeks = [];
    days.forEach(function (d) {
      var dt = parseDay(d.day), wd = (dt.getDay() + 6) % 7;
      var mon = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate() - wd);
      var key = mon.toDateString();
      var w = weeks.length && weeks[weeks.length - 1].key === key ? weeks[weeks.length - 1] : null;
      if (!w) { w = { key: key, kw: isoWeek(dt), from: d.day, to: d.day, n: 0, min: 0, partial: wd !== 0 }; weeks.push(w); }
      w.to = d.day; w.n += d.training_n || 0; w.min += d.training_min || 0;
    });
    if (weeks.length) weeks[weeks.length - 1].partial = weeks[weeks.length - 1].partial || ((parseDay(weeks[weeks.length - 1].to).getDay() + 6) % 7) !== 6;
    var plan = D.training_plan || 4;
    out.train = {
      title: T.train, sub: T.train_sub, empty: !days.some(function (d) { return d.training_n > 0; }),
      option: function (P) {
        var s = bar(T.sessions, weeks.map(function (w) { return w.n; }), P.c[0], { barMaxWidth: 28 });
        s.markLine = refLine(P, plan, T.plan + " " + plan);
        return {
          grid: grid({ top: 16, right: 52 }),
          tooltip: tooltip(P, "axis", "shadow", function (ps) {
            var w = weeks[ps[0].dataIndex];
            return tipHtml(T.wk + w.kw + " · " + fmtDay(w.from, DAY_SHORT) + " – " + fmtDay(w.to, DAY_SHORT), [
              { color: P.c[0], label: T.sessions, value: w.n + " / " + plan },
              { label: T.minutes, value: num(w.min) }]);
          }),
          xAxis: Object.assign(xDays(P, weeks.map(function (w) { return T.wk + w.kw; })), {
            axisLabel: { color: P.text2, fontSize: 11, hideOverlap: true, margin: 10 }
          }),
          yAxis: yVal(P, { minInterval: 1, max: function (v) { return Math.max(plan + 1, v.max); } }),
          series: [s]
        };
      },
      table: function () {
        return {
          head: [T.week, T.sessions, T.minutes], num: [-1, 1, 2],
          rows: weeks.map(function (w) { return [T.wk + w.kw + " (" + fmtDay(w.from, DAY_SHORT) + " – " + fmtDay(w.to, DAY_SHORT) + ")", w.n + " / " + plan, num(w.min)]; })
        };
      }
    };

    // ---- strength: top-set kg per main exercise
    var lifts = (D.lifts && D.lifts.exercises) || {}, exs = Object.keys(lifts).slice(0, 4);
    var others = (D.lifts && D.lifts.others) || [];
    var liftAt = {};
    exs.forEach(function (ex) { liftAt[ex] = {}; lifts[ex].forEach(function (p) { liftAt[ex][p.day] = p; }); });
    out.lifts = {
      title: T.lifts, sub: T.lifts_sub, empty: !exs.length,
      note: others.length ? T.others + ": " + others.join(", ") : null,
      option: function (P) {
        return {
          grid: grid({ top: 36 }),
          legend: legend(P, exs.map(function (ex) { return { name: ex, icon: LINE_ICON }; }), exs.length > 3),
          tooltip: dayAxisTip(P, function (d) {
            return exs.filter(function (ex) { return liftAt[ex][d.day]; }).map(function (ex) {
              var p = liftAt[ex][d.day];
              return { color: P.c[exs.indexOf(ex)], label: ex,
                value: num(p.top_kg, p.top_kg % 1 ? 1 : 0) + " kg" + (p.top_reps ? " × " + p.top_reps : "") + (isNum(p.e1rm) ? " · " + T.e1rm + " " + num(p.e1rm) : "") };
            });
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(2)),
          series: exs.map(function (ex, i) {
            return line(ex, keys.map(function (k) { return liftAt[ex][k] ? liftAt[ex][k].top_kg : null; }), P.c[i], { showSymbol: true, smooth: false });
          })
        };
      },
      table: function () {
        var rows = [];
        exs.forEach(function (ex) {
          lifts[ex].forEach(function (p) { rows.push([fmtDay(p.day, DAY_LONG), ex, num(p.top_kg, 1), p.top_reps || "–", isNum(p.e1rm) ? num(p.e1rm, 1) : "–"]); });
        });
        return { head: [T.day, "", "kg", "reps", T.e1rm], num: [-1, -1, 2, 3, 4], rows: rows };
      }
    };

    // ---- body measures (cards only when data exists)
    var M = D.measures || {};
    function measureLine(list, key) {
      var at = {};
      list.forEach(function (p) { at[p.day] = p; });
      return keys.map(function (k) { return at[k] ? at[k][key] : null; });
    }
    if ((M.waist_cm || []).length) out.waist = {
      title: T.waist, sub: T.waist_sub,
      option: function (P) {
        return {
          grid: grid({ top: 16 }),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var i = ps[0].dataIndex, v = ps[0].value;
            return tipHtml(fmtDay(keys[i], DAY_LONG), [{ color: P.c[0], label: T.waist, value: isNum(v) ? num(v, 1) + " cm" : "–" }]);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(2)),
          series: [line(T.waist, measureLine(M.waist_cm, "value"), P.c[0], { showSymbol: true })]
        };
      },
      table: function () { return { head: [T.day, "cm"], num: [-1, 1], rows: M.waist_cm.map(function (p) { return [fmtDay(p.day, DAY_LONG), num(p.value, 1)]; }) }; }
    };
    if ((M.bp || []).length) out.bp = {
      title: T.bp, sub: T.bp_sub,
      option: function (P) {
        var at = {};
        M.bp.forEach(function (p) { at[p.day] = p; });
        return {
          grid: grid({ top: 36 }),
          legend: legend(P, [{ name: T.sys, icon: LINE_ICON }, { name: T.dia, icon: LINE_ICON }]),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var k = keys[ps[0].dataIndex], p = at[k];
            if (!p) return tipHtml(fmtDay(k, DAY_LONG), [{ label: T.bp, value: "–" }]);
            var r = [{ color: P.c[0], label: T.sys, value: p.sys + " mmHg" }, { color: P.c[1], label: T.dia, value: p.dia + " mmHg" }];
            if (isNum(p.pulse)) r.push({ label: T.pulse, value: p.pulse + " /min" });
            return tipHtml(fmtDay(k, DAY_LONG), r);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(2)),
          series: [line(T.sys, measureLine(M.bp, "sys"), P.c[0], { showSymbol: true }),
            line(T.dia, measureLine(M.bp, "dia"), P.c[1], { showSymbol: true })]
        };
      },
      table: function () {
        return { head: [T.day, T.sys, T.dia, T.pulse], num: [-1, 1, 2, 3],
          rows: M.bp.map(function (p) { return [fmtDay(p.day, DAY_LONG), String(p.sys), String(p.dia), isNum(p.pulse) ? String(p.pulse) : "–"]; }) };
      }
    };
    if ((M.resting_hr || []).length) out.rhr = {
      title: T.rhr, sub: T.rhr_sub,
      option: function (P) {
        return {
          grid: grid({ top: 16 }),
          tooltip: tooltip(P, "axis", "line", function (ps) {
            var i = ps[0].dataIndex, v = ps[0].value;
            return tipHtml(fmtDay(keys[i], DAY_LONG), [{ color: P.c[0], label: T.rhr, value: isNum(v) ? num(v) + " /min" : "–" }]);
          }),
          xAxis: xDays(P, keys), yAxis: yVal(P, pad(2)),
          series: [line(T.rhr, measureLine(M.resting_hr, "value"), P.c[0], { showSymbol: true })]
        };
      },
      table: function () { return { head: [T.day, "/min"], num: [-1, 1], rows: M.resting_hr.map(function (p) { return [fmtDay(p.day, DAY_LONG), num(p.value)]; }) }; }
    };

    out.pantry = { title: T.pantry, sub: T.pantry_sub, empty: !(D.pantry || []).length, custom: renderPantry };
    out.cookbook = { title: T.cookbook, sub: T.cookbook_sub, empty: !(D.cookbook || []).length, custom: renderCookbook };
    return out;
  }

  // ------------------------------------------------------------------------------------------
  // custom cards: pantry, cookbook
  // ------------------------------------------------------------------------------------------

  function renderPantry(body, D) {
    var wrap = el("div", "table-wrap pantry-table"), table = el("table"), thead = el("thead"), tr = el("tr");
    [[T.item, ""], ["Status", ""], [T.left, "num"], [T.storage, "hide-sm"], [T.expiry, "num"]].forEach(function (h) {
      tr.appendChild(el("th", h[1] || null, h[0]));
    });
    thead.appendChild(tr);
    table.appendChild(thead);
    var tb = el("tbody");
    D.pantry.forEach(function (it) {
      var row = el("tr"), name = el("td");
      name.appendChild(el("div", "item-name", it.name || it.item_id));
      var flags = [];
      if (it.opened) flags.push(T.opened);
      if (it.expires_est) flags.push(T.est);
      if (flags.length) name.appendChild(el("div", "item-meta", flags.join(" · ")));
      if ((it.status === "check" || it.status === "discard") && it.check_hint) name.appendChild(el("div", "item-hint", it.check_hint));
      row.appendChild(name);
      var st = el("td"), chip = el("span", "chip " + it.status);
      chip.appendChild(el("i", null, STATUS_ICON[it.status] || ""));
      chip.appendChild(document.createTextNode(T["status_" + it.status] || it.status));
      st.appendChild(chip);
      row.appendChild(st);
      var dec = it.unit === "pcs" ? 0 : (it.remaining % 1 ? 1 : 0);
      row.appendChild(el("td", "num", isNum(it.remaining) ? num(it.remaining, dec) + " " + (it.unit === "pcs" ? "" : it.unit) : "–"));
      row.appendChild(el("td", "hide-sm", T[it.storage === "pantry" ? "pantry_store" : it.storage] || it.storage || "–"));
      var dl = it.days_left;
      row.appendChild(el("td", "num", dl == null ? T.no_date : dl === 0 ? T.today : dl > 0 ? tpl(T.days_left, { n: dl }) : tpl(T.days_past, { n: -dl })));
      tb.appendChild(row);
    });
    table.appendChild(tb);
    wrap.appendChild(table);
    body.appendChild(wrap);
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

  function renderCookbook(body, D) {
    var ul = el("ul", "recipes");
    D.cookbook.forEach(function (r) {
      var li = el("li");
      li.appendChild(el("div", "recipe-name", r.name || "–"));
      var meta = [fmtDay(r.day, DAY_SHORT)];
      if (r.cuisine) meta.push(r.cuisine);
      meta.push(T[r.status] || r.status || "");
      li.appendChild(el("div", "recipe-meta", meta.filter(Boolean).join(" · ")));
      var sc = el("div", "recipe-scores");
      var a = el("span"); a.title = T.simplicity; a.appendChild(stars(r.simplicity));
      var b = el("span"); b.title = T.nutrition; b.appendChild(stars(r.nutrition_score));
      var lab1 = el("span", "sr-only", T.simplicity + " "), lab2 = el("span", "sr-only", T.nutrition + " ");
      a.insertBefore(lab1, a.firstChild); b.insertBefore(lab2, b.firstChild);
      var rt = el("span", "rating", r.rating === "up" ? "👍" : r.rating === "down" ? "👎" : "–");
      rt.title = T.rating;
      sc.appendChild(a); sc.appendChild(b); sc.appendChild(rt);
      li.appendChild(sc);
      ul.appendChild(li);
    });
    var legendRow = el("p", "note", "★ " + T.simplicity + " · ★ " + T.nutrition + " · 👍/👎 " + T.rating);
    body.appendChild(ul);
    body.appendChild(legendRow);
  }

  // ------------------------------------------------------------------------------------------
  // cards & sections
  // ------------------------------------------------------------------------------------------

  var ICON_TABLE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M3 10h18M3 15h18M10 4v16"/></svg>';
  var ICON_CHART = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>';
  var ICON_EMPTY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3 12h4l2.5-6 5 12 2.5-6h4"/></svg>';

  function buildTable(t) {
    var table = el("table", "data-table"), thead = el("thead"), tr = el("tr");
    t.head.forEach(function (h, i) { tr.appendChild(el("th", t.num.indexOf(i) >= 0 ? "num" : null, h)); });
    thead.appendChild(tr);
    table.appendChild(thead);
    var tb = el("tbody");
    t.rows.forEach(function (r) {
      var row = el("tr");
      r.forEach(function (v, i) { row.appendChild(el("td", t.num.indexOf(i) >= 0 ? "num" : null, v == null ? "–" : String(v))); });
      tb.appendChild(row);
    });
    table.appendChild(tb);
    return table;
  }

  function addCard(gridEl, spec, D, cls) {
    var card = el("article", "card" + (cls ? " " + cls : "") + (spec.cls ? " " + spec.cls : ""));
    var head = el("div", "card-head"), titles = el("div");
    var h3 = el("h3", null, spec.title);
    h3.id = "c" + Math.random().toString(36).slice(2, 9);
    titles.appendChild(h3);
    if (spec.sub) titles.appendChild(el("p", null, spec.sub));
    head.appendChild(titles);
    card.appendChild(head);
    card.setAttribute("aria-labelledby", h3.id);
    gridEl.appendChild(card);

    if (spec.empty) {
      var e = el("div", "empty");
      e.innerHTML = ICON_EMPTY;
      e.appendChild(el("span", null, T.empty));
      card.appendChild(e);
      return;
    }
    if (spec.custom) { spec.custom(card, D); return; }

    var chartEl = el("div", "chart");
    chartEl.setAttribute("role", "img");
    chartEl.setAttribute("aria-label", spec.title + (spec.sub ? " – " + spec.sub : ""));
    card.appendChild(chartEl);
    var wrap = el("div", "table-wrap");
    wrap.hidden = true;
    card.appendChild(wrap);
    if (spec.note) card.appendChild(el("p", "note", spec.note));

    var btn = el("button", "toggle");
    btn.type = "button";
    btn.setAttribute("aria-pressed", "false");
    var setBtn = function (tableOn) {
      btn.innerHTML = tableOn ? ICON_CHART : ICON_TABLE;
      btn.appendChild(document.createTextNode(tableOn ? T.chart : T.table));
    };
    setBtn(false);
    head.appendChild(btn);

    var entry = { el: chartEl, spec: spec, inst: null, wide: null };
    state.charts.push(entry);
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

  function renderChart(entry, P) {
    var w = entry.el.clientWidth || 600;
    entry.wide = w >= 520;
    var opt = entry.spec.option(P, w);
    opt.textStyle = { fontFamily: P.font, color: P.text2 };
    opt.animationDuration = 450;
    opt.animationDurationUpdate = 250;
    if (!entry.inst) entry.inst = echarts.init(entry.el, null, { renderer: "svg" });
    entry.inst.setOption(opt, { notMerge: true });
  }

  function renderAllCharts() {
    var P = pal();
    state.charts.forEach(function (c) { renderChart(c, P); });
  }

  function disposeCharts() {
    state.charts.forEach(function (c) { if (c.inst) c.inst.dispose(); });
    state.charts = [];
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
    var dot = el("span", "kpi-dot");
    dot.style.background = "var(" + o.color + ")";
    lab.appendChild(dot);
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
  }

  function renderKpis(D) {
    var root = document.getElementById("kpis"), days = D.days;
    root.innerHTML = "";
    var last = function (k) { for (var i = days.length - 1; i >= 0; i--) if (isNum(days[i][k])) return i; return -1; };
    var col = function (k) { return days.map(function (d) { return d[k]; }); };

    // weight: 7-day mean, delta vs 7 days earlier
    var wi = last("weight_7d"), wv = wi >= 0 ? days[wi].weight_7d : null;
    var wPrev = wi >= 7 ? days[wi - 7].weight_7d : null;
    kpi(root, { label: T.kpi_weight, color: "--c1", value: num(wv, 1), unit: "kg",
      sub: isNum(wv) && isNum(wPrev) ? signed(wv - wPrev, 1) + " kg " + T.kpi_weight_sub_delta : T.kpi_weight_sub,
      spark: col("weight_7d") });

    // protein mean per day with meals, vs target
    var pm = mean(col("protein_g")), pt = D.targets && D.targets.protein_g;
    var ptLo = isNum(pt) ? pt : Array.isArray(pt) ? pt[0] : D.targets && D.targets.protein_g_min;
    kpi(root, { label: T.kpi_protein, color: "--c3", value: num(pm), unit: "g",
      sub: isNum(ptLo) && isNum(pm) ? T.kpi_protein_target + " " + num(ptLo) + " g · " + Math.round(pm / ptLo * 100) + " %" : T.kpi_protein_sub,
      spark: col("protein_g") });

    // sleep
    var sm = mean(col("sleep_h")), sq = mean(col("sleep_quality"));
    kpi(root, { label: T.kpi_sleep, color: "--c7", value: isNum(sm) ? num(sm, 1) : "–", unit: "h",
      sub: isNum(sq) ? T.kpi_sleep_q + " " + num(sq, 1) + " / 5" : "", spark: col("sleep_h") });

    // substances per logged day; tobacco; delta vs previous equal period
    var kinds = Object.keys(D.substance_kinds || {});
    var useLabel = kinds.length === 1 && T["kpi_" + kinds[0]] ? T["kpi_" + kinds[0]] : T.kpi_use;
    var logged = days.filter(function (d) { return d.logged; });
    var subTotal = days.reduce(function (a, d) { return a + (d.substance_n || 0); }, 0);
    var tobTotal = days.reduce(function (a, d) { return a + (d.tobacco_n || 0); }, 0);
    var rate = logged.length ? subTotal / logged.length : null;
    var sub = T.kpi_tobacco + " " + (logged.length ? num(tobTotal / logged.length, 1) : "–");
    var pv = D.previous;
    if (isNum(rate) && pv && pv.days_logged > 0) sub += " · " + signed(rate - pv.substance_n / pv.days_logged, 1) + " " + T.kpi_prev;
    kpi(root, { label: useLabel, color: "--c2", value: isNum(rate) ? num(rate, 1) : "–", sub: logged.length ? sub : "",
      spark: days.map(function (d) { return d.logged ? d.substance_n : null; }) });

    // training this week
    var plan = D.training_plan || 4, wk = D.week || { training_n: 0, training_min: 0 };
    kpi(root, { label: T.kpi_train, color: "--c1", value: wk.training_n + " / " + plan,
      sub: tpl(T.kpi_train_sub, { n: plan }) + (wk.training_min ? " · " + num(wk.training_min) + " min" : ""),
      pips: [Math.min(wk.training_n, Math.max(plan, wk.training_n)), Math.max(plan, wk.training_n)] });
  }

  // ------------------------------------------------------------------------------------------
  // page
  // ------------------------------------------------------------------------------------------

  function render(D) {
    T = I18N[(D.language || "en").slice(0, 2)] || I18N.en;
    document.documentElement.lang = (D.language || "en").slice(0, 2);
    applyStaticText();
    var p = D.period, now = new Date();
    var hhmm = (now.getHours() < 10 ? "0" : "") + now.getHours() + ":" + (now.getMinutes() < 10 ? "0" : "") + now.getMinutes();
    document.getElementById("subtitle").textContent =
      fmtDay(p.from, DAY_SHORT) + " – " + fmtDay(p.to, { day: "numeric", month: "short", year: "numeric" }) +
      " · " + T.updated + " " + hhmm;
    document.querySelectorAll("#period button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-days") === p.key));
    });

    renderKpis(D);
    disposeCharts();
    var root = document.getElementById("sections");
    root.innerHTML = "";
    if (!p.days_logged) {
      var bn = el("div", "banner");
      bn.appendChild(el("b", null, T.no_entries));
      bn.appendChild(el("span", null, T.no_entries_hint));
      root.appendChild(bn);
    }
    var S = specs(D);

    var g = section(root, T.sec_body, T.sec_body_sub);
    var ms = ["waist", "bp", "rhr"].filter(function (k) { return S[k]; });
    addCard(g, S.weight, D, ms.length === 1 ? "wide" : "full");
    ms.forEach(function (k, i) { addCard(g, S[k], D, ms.length === 2 && i === 1 ? "wide" : ""); });

    g = section(root, T.sec_food, T.sec_food_sub, "grid-2");
    addCard(g, S.protein, D); addCard(g, S.kcal, D); addCard(g, S.water, D); addCard(g, S.coffee, D);

    g = section(root, T.sec_sleep, T.sec_sleep_sub);
    addCard(g, S.sleep, D); addCard(g, S.svu, D, "wide");

    g = section(root, T.sec_use, T.sec_use_sub, "grid-2");
    addCard(g, S.trig, D, "tall"); addCard(g, S.heat, D);

    g = section(root, T.sec_mind, T.sec_mind_sub);
    addCard(g, S.mind, D); addCard(g, S.train, D); addCard(g, S.lifts, D);

    g = section(root, T.sec_kitchen, T.sec_kitchen_sub);
    addCard(g, S.pantry, D, "wide"); addCard(g, S.cookbook, D);

    var foot = document.getElementById("foot");
    foot.innerHTML = "";
    [T.foot_live, T.foot_raw, T.foot_credit].forEach(function (s) { foot.appendChild(el("span", null, s)); });

    requestAnimationFrame(renderAllCharts);
  }

  function applyStaticText() {
    document.querySelectorAll("#period button").forEach(function (b) {
      var d = b.getAttribute("data-days");
      b.textContent = d === "all" ? T.all : d + " " + T.days;
    });
    document.getElementById("period").setAttribute("aria-label", T.period);
    document.getElementById("privacy-text").textContent = T.local_only + " · " + location.hostname;
    updateThemeButton();
  }

  function showError(msg) {
    var root = document.getElementById("sections");
    root.innerHTML = "";
    var bn = el("div", "banner");
    bn.appendChild(el("b", null, T.load_error));
    bn.appendChild(el("span", null, msg));
    root.appendChild(bn);
  }

  function load(period) {
    var url = "api/data" + (period ? "?days=" + encodeURIComponent(period) : "");
    state.loading = true;
    document.body.setAttribute("aria-busy", "true");
    return fetch(url, { cache: "no-store" }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || r.status);
        return j;
      });
    }).then(function (D) {
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

  function updateThemeButton() {
    var b = document.getElementById("theme"), dark = effectiveTheme() === "dark";
    b.innerHTML = dark
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>';
    b.setAttribute("aria-label", dark ? T.theme_light : T.theme_dark);
    b.title = b.getAttribute("aria-label");
  }

  function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    store("bos-theme", t);
    updateThemeButton();
    renderAllCharts();
  }

  // ------------------------------------------------------------------------------------------
  // wiring
  // ------------------------------------------------------------------------------------------

  document.getElementById("theme").addEventListener("click", function () {
    setTheme(effectiveTheme() === "dark" ? "light" : "dark");
  });
  if (mq) {
    var onScheme = function () { updateThemeButton(); renderAllCharts(); };
    if (mq.addEventListener) mq.addEventListener("change", onScheme); else if (mq.addListener) mq.addListener(onScheme);
  }
  document.getElementById("period").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b || state.loading) return;
    var d = b.getAttribute("data-days");
    store("bos-period", d);
    load(d);
  });

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      var P = null;
      state.charts.forEach(function (c) {
        if (!c.inst || c.el.hidden) return;
        var wide = (c.el.clientWidth || 600) >= 520;
        if (wide !== c.wide) { P = P || pal(); renderChart(c, P); } else c.inst.resize();
      });
    }, 120);
  });

  updateThemeButton();
  var saved = store("bos-period");
  load(saved === "14" || saved === "30" || saved === "90" || saved === "all" ? saved : null);
})();
