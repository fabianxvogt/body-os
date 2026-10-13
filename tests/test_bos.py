"""Tests for tools/bos.py. Run: python3 -m unittest discover -s tests

All tests work on temporary copies; examples/demo-me is never written to.
"""

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import zipfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bos  # noqa: E402

DEMO = os.path.join(ROOT, "examples", "demo-me")
DEMO_HH = os.path.join(ROOT, "examples", "demo-household")
DEMO_TODAY = "2026-10-13"
BLS_ZIP = os.path.join(ROOT, "data", "sources", "BLS_4_0_2025_DE.zip")


def run(*argv):
    """Run the CLI in-process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bos.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def demo_events(subdir="log"):
    evs = []
    for base, _, files in os.walk(os.path.join(DEMO, subdir)):
        for f in sorted(files):
            if f.endswith(".jsonl"):
                with open(os.path.join(base, f)) as fh:
                    evs += [json.loads(line) for line in fh if line.strip()]
    return evs


class TempMe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-test-")
        self.me = os.path.join(self.tmp, "me")
        shutil.copytree(DEMO, self.me)
        self.data = os.path.join(self.tmp, "data")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bos(self, *argv, today=DEMO_TODAY):
        args = ["--me", self.me, "--data", self.data]
        if today:
            args += ["--today", today]
        return run(*(args + list(argv)))


class TestLog(TempMe):
    def test_fills_id_ts_src_and_routes_to_current_month(self):
        code, out, _ = self.bos("log", '{"type": "weight", "kg": 80.5}')
        self.assertEqual(code, 0)
        ev = json.loads(out.splitlines()[0])
        self.assertRegex(ev["id"], r"^weight-\d{14}-[0-9a-f]{4}$")
        ts = bos.parse_ts(ev["ts"])
        self.assertIsNotNone(ts.tzinfo)
        self.assertEqual(ev["src"], "chat")
        self.assertEqual(ev["id"][7:21], ts.strftime("%Y%m%d%H%M%S"))
        path = os.path.join(self.me, "log", "%04d" % ts.year, "%04d-%02d.jsonl" % (ts.year, ts.month))
        with open(path) as f:
            self.assertIn(ev["id"], f.read().splitlines()[-1])
        self.assertEqual(list(ev)[:3], ["id", "ts", "type"])

    def test_month_routing_by_event_ts_and_batch(self):
        batch = [{"type": "drink", "kind": "water", "ml": 300, "ts": "2025-12-31T23:30:00+01:00"},
                 {"type": "checkin", "mood": 4, "ts": "2026-01-01T00:10:00+01:00"}]
        code, _, _ = self.bos("log", json.dumps(batch))
        self.assertEqual(code, 0)
        dec = os.path.join(self.me, "log", "2025", "2025-12.jsonl")
        jan = os.path.join(self.me, "log", "2026", "2026-01.jsonl")
        self.assertEqual(len(bos.load_events(dec)), 1)
        self.assertEqual(bos.load_events(jan)[0]["type"], "checkin")

    def test_naive_ts_gets_settings_offset(self):
        code, out, _ = self.bos("log", '{"type": "weight", "kg": 77, "ts": "2026-07-01T07:30"}')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.splitlines()[0])["ts"], "2026-07-01T07:30:00+02:00")  # Europe/Berlin summer

    def test_aware_ts_is_converted_to_local_time(self):
        code, out, _ = self.bos("log", '{"type": "weight", "kg": 77, "ts": "2026-11-04T23:30:00Z"}')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.splitlines()[0])["ts"], "2026-11-05T00:30:00+01:00")

    def test_meals_without_numbers_are_unknown_not_zero(self):
        self.bos("log", '[{"type": "meal", "desc": "pasta", "ts": "2026-08-02T12:00"},'
                        ' {"type": "meal", "desc": "rice", "kcal": 800, "ts": "2026-08-01T12:00"}]')
        code, out, _ = self.bos("summary", "--from", "2026-08-01", "--to", "2026-08-02", "--json", today=None)
        self.assertEqual(code, 0)
        days = {d["day"]: d for d in json.loads(out)["days"]}
        self.assertIsNone(days["2026-08-02"]["kcal"])
        self.assertEqual(days["2026-08-01"]["kcal"], 800)

    def test_dry_run_writes_nothing(self):
        code, _, _ = self.bos("log", "--dry-run", '{"type": "weight", "kg": 80, "ts": "2027-02-01T08:00:00+01:00"}')
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(self.me, "log", "2027")))

    def test_validation_errors_reject_whole_batch(self):
        bad = [
            {"type": "weight", "kg": 80, "ts": "2027-03-01T08:00:00+01:00"},  # valid, but batch fails
            {"type": "weight"},                                                # missing kg
            {"type": "sleep", "bed": "2027-03-01T23:00:00+01:00", "wake": "2027-03-02T07:00:00+01:00", "quality": 7},
            {"type": "checkin"},                                               # no ratings
            {"type": "teleport"},                                              # unknown type
            {"type": "drink", "kind": "lava", "ml": 100},
            {"type": "substance", "kind": "cigarette", "tobacco": "yes"},
        ]
        code, _, err = self.bos("log", json.dumps(bad))
        self.assertEqual(code, 2)
        for frag in ("event 1: missing 'kg'", "'quality'=7 out of range", "event 3: checkin needs",
                     "event 4: 'type'='teleport'", "'kind'='lava'", "'tobacco' must be true/false"):
            self.assertIn(frag, err)
        self.assertFalse(os.path.exists(os.path.join(self.me, "log", "2027")))

    def test_validator_unit_rules(self):
        ok = {"id": "x", "ts": "2026-10-01T08:00:00+02:00", "type": "measure", "metric": "bp", "sys": 120, "dia": 80}
        self.assertEqual(bos.validate_log_event(ok), [])
        self.assertTrue(bos.validate_log_event(dict(ok, ts="2026-10-01T08:00:00")))  # no offset
        sleep = {"id": "s", "ts": "2026-10-01T07:00:00+02:00", "type": "sleep",
                 "bed": "2026-10-01T07:00:00+02:00", "wake": "2026-10-01T06:00:00+02:00"}
        self.assertIn("'wake' must be after 'bed'", bos.validate_log_event(sleep))
        tr = {"id": "t", "ts": "2026-10-01T07:00:00+02:00", "type": "training", "kind": "strength",
              "sets": [{"ex": "squat", "kg": 60, "reps": [8, "eight"]}]}
        self.assertIn("sets[0].reps must be a list of integers", bos.validate_log_event(tr))

    def test_validate_reports_line_numbers(self):
        path = os.path.join(self.me, "log", "2026", "2026-10.jsonl")
        with open(path, "a") as f:
            f.write("{not json\n")
            f.write('{"id": "w1", "ts": "2026-11-02T08:00:00+01:00", "type": "weight", "kg": 70}\n')
        with open(path) as f:
            n = sum(1 for _ in f)
        code, out, _ = self.bos("validate")
        self.assertEqual(code, 1)
        self.assertIn("log/2026/2026-10.jsonl:%d: invalid JSON" % (n - 1), out)
        self.assertIn("log/2026/2026-10.jsonl:%d: ts 2026-11-02T08:00:00+01:00 belongs in 2026-11.jsonl" % n, out)

    def test_demo_is_valid(self):
        code, out, _ = run("--me", DEMO, "validate")
        self.assertEqual(code, 0, out)


class TestPantry(TempMe):
    def test_demo_statuses(self):
        ctx = bos.Ctx(self.me, self.data, DEMO_TODAY)
        st = {s["item_id"]: s for s in bos.pantry_state(ctx)}
        expected = {
            "oats-0001": "ok", "rice-0001": "ok", "eggs-0001": "ok",
            "milk-0001": "soon", "tofu-0001": "soon",
            "cheese-0001": "check", "banana-0001": "check",
            "yogurt-0001": "discard", "spinach-0001": "discard", "jam-0001": "discard",
            "chicken-0001": "gone", "bread-0001": "gone", "tomato-0001": "gone",
            # added for the dashboard demo: groceries from other stores, waste, a freezer item
            "thighs-0001": "ok", "mushroom-0001": "ok", "berries-0001": "ok", "skyr-0001": "ok",
            "salad-0001": "gone", "carrot-0001": "gone", "sourdough-0001": "gone",
        }
        self.assertEqual({k: v["status"] for k, v in st.items()}, expected)
        self.assertEqual(st["oats-0001"]["remaining"], 880)
        self.assertEqual(st["rice-0001"]["remaining"], 600)
        self.assertEqual(st["tofu-0001"]["expires"], "2026-10-15")  # open event re-estimates expiry
        self.assertTrue(st["milk-0001"]["opened"])
        self.assertEqual(st["salad-0001"]["gone_at"], "2026-10-08")  # discard date, for waste stats
        self.assertNotIn("gone_at", st["oats-0001"])
        code, out, _ = self.bos("pantry")
        self.assertEqual(code, 0)
        self.assertNotIn("chicken breast", out)
        self.assertTrue(out.splitlines()[1].startswith("discard"))
        self.assertIn("check: slimy leaves", out)
        code, out, _ = self.bos("pantry", "--all")
        self.assertIn("chicken breast", out)

    def test_status_rules_and_grace(self):
        ctx = bos.Ctx(self.me, self.data, "2026-10-13")
        ctx.settings = {}  # defaults: best_before 7, none 2

        def status(kind, expires, **kw):
            return bos.item_status(ctx, dict({"date_kind": kind, "expires": expires}, **kw))[0]
        self.assertEqual(status("best_before", "2026-10-16"), "ok")
        self.assertEqual(status("best_before", "2026-10-15"), "soon")
        self.assertEqual(status("use_by", "2026-10-13"), "soon")
        self.assertEqual(status("use_by", "2026-10-12"), "discard")
        self.assertEqual(status("best_before", "2026-10-06"), "check")    # 7 days past
        self.assertEqual(status("best_before", "2026-10-05"), "discard")  # 8 days past
        self.assertEqual(status("none", "2026-10-11"), "check")           # 2 days past
        self.assertEqual(status("none", "2026-10-10"), "discard")         # 3 days past
        self.assertEqual(status("none", "2026-10-10", grace_days=5), "check")
        self.assertEqual(status("use_by", "2026-10-01", gone=True), "gone")
        ctx.settings = {"pantry": {"grace_days": {"best_before": 30}}}
        self.assertEqual(status("best_before", "2026-10-01"), "check")

    def test_pantry_log_generates_item_ids_and_checks_references(self):
        buy = {"type": "purchase", "ts": "2026-10-01T18:00:00+02:00", "items": [
            {"name": "Crème fraîche", "qty": 200, "unit": "g", "category": "dairy", "storage": "fridge",
             "date_kind": "use_by", "expires": "2026-10-20"}]}
        code, out, _ = self.bos("pantry-log", json.dumps(buy))
        self.assertEqual(code, 0)
        item_id = json.loads(out.splitlines()[0])["items"][0]["item_id"]
        self.assertRegex(item_id, r"^creme-fraiche-[0-9a-f]{4}$")
        code, _, _ = self.bos("pantry-log", json.dumps({"type": "consume", "item_id": item_id, "qty": 50}))
        self.assertEqual(code, 0)
        code, _, err = self.bos("pantry-log", '{"type": "consume", "item_id": "nope-0000"}')
        self.assertEqual(code, 2)
        self.assertIn("unknown item_id", err)
        early = {"type": "consume", "item_id": item_id, "ts": "2026-09-01T08:00:00+02:00"}
        code, _, err = self.bos("pantry-log", json.dumps(early))
        self.assertEqual(code, 2)
        self.assertIn("before the purchase", err)
        ctx = bos.Ctx(self.me, self.data, DEMO_TODAY)
        st = {s["item_id"]: s for s in bos.pantry_state(ctx)}
        self.assertEqual(st[item_id]["remaining"], 150)
        self.assertEqual(st[item_id]["status"], "ok")


class TestSummary(TempMe):
    def test_numbers_match_raw_demo_data(self):
        ctx = bos.Ctx(self.me, self.data, DEMO_TODAY)
        s = bos.build_summary(ctx, dt.date(2026, 9, 30), dt.date(2026, 10, 13))
        p = s["period"]
        raw = demo_events()
        self.assertEqual(p["days"], 14)
        self.assertEqual(p["days_logged"], 14)
        self.assertEqual(p["training_sessions"], sum(1 for e in raw if e["type"] == "training"))
        cigs = sum(e.get("count", 1) for e in raw if e["type"] == "substance" and e["kind"] == "cigarette")
        self.assertEqual(p["substances_total"]["cigarette"], cigs)
        self.assertEqual(p["tobacco_total"], sum(e.get("count", 1) for e in raw if e["type"] == "substance" and e["tobacco"]))
        self.assertEqual(p["symptoms"], 2)
        self.assertAlmostEqual(p["alcohol_units_total"], 8.0)
        self.assertEqual(p["weight_first"], 78.4)
        self.assertEqual(p["weight_last"], 77.3)
        self.assertLess(p["weight_slope_kg_per_week"], 0)
        day = {r["day"]: r for r in s["days"]}["2026-10-04"]
        prot = sum(e.get("protein_g", 0) for e in raw if e["type"] == "meal" and e["ts"].startswith("2026-10-04"))
        self.assertEqual(day["protein_g"], prot)
        self.assertIsNone(day["weight_kg"])
        self.assertEqual(day["alcohol_units"], 4.0)
        # sleep is attributed to the wake-up day; 2026-10-02 follows the 10-01 evening joint
        d2 = {r["day"]: r for r in s["days"]}["2026-10-02"]
        self.assertAlmostEqual(d2["sleep_h"], 6.5)
        self.assertEqual(d2["wakeups"], 2)
        self.assertEqual({r["day"]: r for r in s["days"]}["2026-10-01"]["last_substance"], "22:40")
        # 7-day trend on 10-13 = mean of weights 10-07..10-13
        ws = [e["kg"] for e in raw if e["type"] == "weight" and "2026-10-07" <= e["ts"][:10] <= "2026-10-13"]
        self.assertAlmostEqual(day and {r["day"]: r for r in s["days"]}["2026-10-13"]["weight_7d"], sum(ws) / len(ws))

    def test_text_output_hides_notes_unless_asked(self):
        code, out, _ = self.bos("summary", "--days", "14")
        self.assertEqual(code, 0)
        self.assertIn("2026-09-30..2026-10-13 (14 days, 14 with entries)", out)
        self.assertNotIn("Fictional note", out)
        self.assertNotIn("headache", out)
        code, out, _ = self.bos("summary", "--days", "14", "--notes")
        self.assertIn("Fictional note", out)
        code, out, _ = self.bos("summary", "--from", "2026-10-01", "--to", "2026-10-02", "--json")
        self.assertEqual(len(json.loads(out)["days"]), 2)


class TestBuild(TempMe):
    def test_build_creates_tables_and_view(self):
        code, _, _ = self.bos("build")
        self.assertEqual(code, 0)
        con = sqlite3.connect(os.path.join(self.data, "body-os.sqlite"))
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
        for t in bos.LOG_TYPES + ("sets", "pantry_items", "pantry_events", "cookbook", "daily"):
            self.assertIn(t, names)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM daily").fetchone()[0], 14)
        raw = demo_events()
        n_sets = sum(len(s["reps"]) for e in raw if e["type"] == "training" for s in e.get("sets", []))
        self.assertEqual(con.execute("SELECT COUNT(*) FROM sets").fetchone()[0], n_sets)
        self.assertEqual(con.execute("SELECT status FROM pantry_items WHERE item_id = 'yogurt-0001'").fetchone()[0], "discard")
        self.assertEqual(con.execute("SELECT per_serving_protein_g FROM cookbook WHERE name = 'chicken rice bowl'").fetchone()[0], 48)
        with open(os.path.join(self.data, "datasette-metadata.json")) as f:
            meta = json.load(f)
        for q in meta["databases"]["body-os"]["queries"].values():
            con.execute(q["sql"]).fetchall()  # every canned query runs
        # extra fields differing only in case, or named like derived columns, must not break build
        run("--me", self.me, "log", '{"type": "note", "text": "a", "Text": "b", "day": "x", "clock": "y"}')
        code, _, _ = self.bos("build")
        self.assertEqual(code, 0)
        # an empty instance still builds (all tables exist with spec columns)
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        code, _, _ = run("--me", empty, "--data", os.path.join(self.tmp, "d2"), "build")
        self.assertEqual(code, 0)


class TestDashboard(TempMe):
    KEYS = ("schema", "today", "period", "language", "modules", "days", "previous", "tabs")
    TABS = {
        "today": ("phase", "next_decision", "checklist", "substances", "due", "pantry_alerts", "week",
                  "training_plan", "focus", "spend_month"),
        "body": ("corridor", "goals", "circumferences", "bp", "vitals", "labs"),
        "nutrition": ("targets", "slots", "meal_times", "macros", "protein_sources", "items_with_protein"),
        "kitchen": ("pantry", "purchases", "waste", "eating_out", "currency", "shopping_list", "cookbook",
                    "cuisines_30d", "ratings", "skills"),
        "sleep": ("nights", "regularity", "vs_last_use", "vs_coffee", "vs_alcohol", "vs_training"),
        "substances": ("active", "substance_kinds", "triggers_total", "trigger_order", "use_times", "baseline",
                       "target_per_day", "streaks", "plan_b", "cost"),
        "training": ("plan", "schedule", "calendar", "lifts", "volume", "endurance", "tests", "next_goals"),
        "journal": ("reviews", "timeline", "decisions"),
    }
    DAY_KEYS = ("day", "logged", "weight_kg", "weight_7d", "sleep_h", "sleep_quality", "wakeups", "meals",
                "meals_missing_kcal", "kcal", "protein_g", "carbs_g", "fat_g", "water_ml", "caffeine_n",
                "last_caffeine", "alcohol_units", "substance_n", "tobacco_n", "triggers", "first_substance",
                "last_substance", "training_n", "training_min", "energy", "mood", "stress")

    def assert_shape(self, d):
        for k in self.KEYS:
            self.assertIn(k, d)
        self.assertEqual(set(d["tabs"]), set(self.TABS))
        self.assertEqual(set(bos.DASHBOARD_TABS), set(self.TABS))
        for tab, keys in self.TABS.items():
            for k in keys:
                self.assertIn(k, d["tabs"][tab], (tab, k))
        for k in self.DAY_KEYS:
            self.assertIn(k, d["days"][0])
        json.dumps(d)  # JSON-serialisable

    def test_demo_data_matches_summary(self):
        ctx = bos.Ctx(self.me, self.data, DEMO_TODAY)
        d = bos.dashboard_data(ctx, "14")
        self.assert_shape(d)
        self.assertEqual((d["period"]["from"], d["period"]["to"], d["period"]["days"]), ("2026-09-30", "2026-10-13", 14))
        p = bos.build_summary(ctx, dt.date(2026, 9, 30), dt.date(2026, 10, 13))
        srows = {r["day"]: r for r in p["days"]}
        for r in d["days"]:
            s = srows[r["day"]]
            for k in ("weight_kg", "substance_n", "tobacco_n", "training_n", "training_min", "caffeine_n",
                      "last_substance", "kcal", "protein_g", "water_ml", "meals", "meals_missing_kcal"):
                self.assertEqual(r[k], s[k], (r["day"], k))
            if s["sleep_h"] is not None:
                self.assertAlmostEqual(r["sleep_h"], s["sleep_h"], places=2)
            if s["weight_7d"] is not None:
                self.assertAlmostEqual(r["weight_7d"], s["weight_7d"], places=3)
            self.assertEqual(sum(r["triggers"].values()), r["substance_n"])
        per = p["period"]
        U = d["tabs"]["substances"]
        self.assertEqual(sum(r["substance_n"] for r in d["days"]), sum(per["substances_total"].values()))
        self.assertEqual(U["substance_kinds"], per["substances_total"])
        self.assertEqual(U["triggers_total"], per["substance_triggers"])
        self.assertEqual(sum(u["count"] for u in U["use_times"]), sum(per["substances_total"].values()))
        self.assertTrue(all(0 <= u["weekday"] <= 6 and 0 <= u["hour"] <= 23 for u in U["use_times"]))
        S = d["tabs"]["sleep"]
        self.assertEqual(len(S["vs_last_use"]), sum(1 for r in p["days"] if r["sleep_h"] is not None))
        svu = {r["day"]: r for r in S["vs_last_use"]}
        self.assertEqual(svu["2026-10-02"]["last_use_prev_evening"], "22:40")  # 10-01 evening joint
        self.assertEqual(svu["2026-10-02"]["minutes_after_18"], 280)
        night = {n["day"]: n for n in S["nights"]}["2026-10-02"]  # bed 00:20, wake 06:50, anchor 20:00
        self.assertEqual((night["bed"], night["bed_min"], night["wake_min"]), ("00:20", 260, 650))
        self.assertIsNotNone(S["regularity"]["bed_sd_min"])
        self.assertEqual(S["vs_alcohol"]["some"]["n"], 2)  # two evenings with beers
        # training: <= 4 exercises, Epley e1RM, top set per day, calendar, plan file
        TR = d["tabs"]["training"]
        ex = TR["lifts"]["exercises"]
        self.assertLessEqual(len(ex), 4)
        sq = {x["day"]: x for x in ex["squat"]}["2026-10-12"]
        self.assertEqual((sq["top_kg"], sq["top_reps"]), (72, 8))
        self.assertAlmostEqual(sq["e1rm"], round(72 * (1 + 8 / 30), 1))
        self.assertEqual(sum(v["kg"] for v in TR["volume"] if v["day"] == "2026-10-12"),
                         72 * 24 + 50 * 22 + 45 * 20)
        self.assertTrue(all(s["category"] in ("strength", "endurance", "other") for s in TR["calendar"]["sessions"]))
        self.assertEqual({g["name"]: g["next_kg"] for g in TR["next_goals"]}["squat"], 74)
        self.assertEqual({g["name"]: g["last_kg"] for g in TR["next_goals"]}["squat"], 72)
        self.assertIn("test_pushups", TR["tests"])
        self.assertTrue(all(e["pace_min_km"] > 0 for e in TR["endurance"] if e["pace_min_km"] is not None))
        # body
        B = d["tabs"]["body"]
        self.assertEqual([m["value"] for m in B["circumferences"]["waist_cm"]["points"]], [86.5, 86.0, 85.5])
        self.assertEqual(len(B["bp"]["points"]), 5)
        self.assertEqual(B["bp"]["latest"]["category"], "normal")  # 121/78
        self.assertEqual(bos.bp_category(118, 77), "optimal")
        self.assertEqual(bos.bp_category(133, 82), "high_normal")
        self.assertEqual(bos.bp_category(125, 91), "hypertension")
        labs = {l["test"]: l for l in B["labs"]}
        self.assertEqual((labs["vitamin_d_25oh"]["flag"], labs["vitamin_d_25oh"]["previous"]), ("low", 18.0))
        self.assertEqual(B["corridor"]["anchor_day"], "2026-10-07")  # first weight of the current phase
        self.assertEqual(B["corridor"]["rate"], [-2.0, -0.5])
        # nutrition: protein band from goals x latest 7-day weight
        N = d["tabs"]["nutrition"]
        lo, hi = N["targets"]["protein_g"]
        ref = N["targets"]["protein_basis"]["weight_kg"]  # rounded to 0.1 kg in the payload
        self.assertAlmostEqual(lo, 1.6 * ref, delta=1)
        self.assertAlmostEqual(hi, 2.0 * ref, delta=1)
        self.assertEqual(N["targets"]["kcal"], [2100, 2400])
        self.assertAlmostEqual(sum(N["macros"]["kcal_pct"].values()), 100, delta=0.2)
        self.assertEqual(N["protein_sources"][0]["name"], "chicken breast")
        self.assertEqual(sum(1 for r in N["slots"] for k in r if k != "day"),
                         sum(1 for r in N["slots"] for k in r if k in bos.MEAL_SLOTS + ("other",)))
        # kitchen: pantry like `bos pantry`, purchases with prices, waste = price x share left
        K = d["tabs"]["kitchen"]
        self.assertEqual([x["item_id"] for x in K["pantry"]],
                         [x["item_id"] for x in bos.pantry_state(ctx) if x["status"] != "gone"])
        self.assertEqual(K["pantry"][0]["status"], "discard")
        waste = {w["name"]: w for w in K["waste"]}
        self.assertEqual((waste["salad mix"]["fraction"], waste["salad mix"]["eur"]), (0.5, 0.9))
        self.assertEqual({p["store"] for p in K["purchases"]}, {"Demo Market", "Demo Discount", "Demo Bio Market"})
        self.assertIn("Shopping list", K["shopping_list"])
        self.assertEqual(len(K["cookbook"]), 7)
        self.assertEqual(K["cookbook"][0]["day"], max(c["day"] for c in K["cookbook"]))
        self.assertEqual([s["skill"] for s in K["skills"]][0], "deglazing")
        self.assertTrue(all(o["eur"] > 0 for o in K["eating_out"]))
        # today: phase, decisions, checklist, due items, focus from the latest weekly review
        TD = d["tabs"]["today"]
        self.assertEqual((TD["phase"]["id"], TD["phase"]["day"], TD["phase"]["of"]), ("tobacco-step-1", 7, 28))
        self.assertEqual((TD["next_decision"]["date"], TD["next_decision"]["days_left"]), ("2026-10-20", 7))
        self.assertTrue(all(c["done"] for c in TD["checklist"]))
        self.assertEqual(TD["due"]["training"], [{"what": "endurance", "days": "tue", "done": True,
                                                  "done_day": "2026-10-13"}])
        self.assertEqual(TD["due"]["training_next"], {"day": "2026-10-15", "what": "strength"})
        due = {m["metric"]: m for m in TD["due"]["measurements"]}
        self.assertEqual(due["waist_cm"]["status"], "done")
        self.assertEqual((due["bp"]["status"], due["bp"]["count"], due["bp"]["of"]), ("open", 1, 2))
        self.assertEqual(TD["focus"]["file"], "2026-W41.md")
        self.assertIn("protein snack", TD["focus"]["text"])
        self.assertEqual(TD["week"]["from"], "2026-10-12")
        self.assertEqual(TD["training_plan"], 4)
        # substances: baseline, streaks, plan B, costs
        self.assertEqual((U["baseline"]["phase_id"], U["baseline"]["days"]), ("baseline", 7))
        base = sum(e.get("count", 1) for e in demo_events() if e["type"] == "substance" and e["tobacco"]
                   and "2026-09-30" <= e["ts"][:10] <= "2026-10-06") / 7
        self.assertAlmostEqual(U["baseline"]["per_day"], base, places=2)
        self.assertEqual(U["target_per_day"], 4)
        self.assertEqual((U["streaks"]["free_days"], U["streaks"]["longest"], U["streaks"]["current"]), (1, 1, 0))
        pb = U["plan_b"]
        self.assertEqual((pb["day"], pb["window_days"], pb["current_days"], pb["status"]), (7, 14, 6, "on_track"))
        self.assertLess(pb["pct_of_baseline"], 90)
        self.assertEqual(U["cost"]["missing"], [])
        self.assertAlmostEqual(U["cost"]["tobacco_eur_per_use"], 0.28)
        self.assertGreater(U["cost"]["saved"]["eur"], 0)
        # 'all' starts at the first logged day; bad periods are rejected
        self.assertEqual(bos.dashboard_data(ctx, "all")["period"]["from"], "2026-09-30")
        self.assertEqual(len(bos.dashboard_data(ctx, 30)["days"]), 30)
        with self.assertRaises(bos.BosError):
            bos.dashboard_data(ctx, "7")

    def test_cost_model(self):
        cs = bos.cost_settings({"costs": {"tobacco_eur_per_g": 0.4, "tobacco_g_per_use": 0.5, "cannabis_eur_per_g": 10,
                                          "cannabis_g_per_use": 0.3, "alcohol_eur_per_unit": 2,
                                          "coffee_eur_per_cup_home": 0.3}})
        c = lambda ev: [(cat, round(eur, 3) if eur is not None else None, est) for cat, eur, est in bos.event_costs(ev, cs)]
        self.assertEqual(c({"type": "substance", "kind": "cigarette", "count": 2}), [("tobacco", 0.4, True)])
        self.assertEqual(c({"type": "substance", "kind": "joint", "tobacco": True, "g": 0.5}),
                         [("tobacco", 0.2, True), ("cannabis", 5.0, True)])
        self.assertEqual(c({"type": "substance", "kind": "joint", "tobacco": False}), [("cannabis", 3.0, True)])
        self.assertEqual(c({"type": "substance", "kind": "cannabis_vape"}), [("cannabis", 3.0, True)])
        self.assertEqual(c({"type": "substance", "kind": "joint", "price_eur": 8}), [("cannabis", 8, False)])
        self.assertEqual(c({"type": "drink", "kind": "alcohol", "ml": 500, "alcohol_units": 2}), [("alcohol", 4, True)])
        self.assertEqual(c({"type": "drink", "kind": "coffee", "ml": 200}), [("coffee", 0.3, True)])
        self.assertEqual(c({"type": "drink", "kind": "coffee", "ml": 200, "price_eur": 3.2}), [("coffee", 3.2, False)])
        self.assertEqual(c({"type": "drink", "kind": "water", "ml": 500}), [])
        self.assertEqual(c({"type": "meal", "desc": "home pasta"}), [])  # groceries count at purchase
        self.assertEqual(c({"type": "meal", "desc": "canteen", "price_eur": 7}), [("out", 7, False)])
        none = bos.cost_settings({})
        self.assertEqual(bos.event_costs({"type": "substance", "kind": "cigarette"}, none), [("tobacco", None, True)])
        self.assertEqual(none["currency"], "EUR")
        # demo month spend adds up and marks estimates
        d = bos.dashboard_data(bos.Ctx(self.me, self.data, DEMO_TODAY), "14")
        sp = d["tabs"]["today"]["spend_month"]
        self.assertEqual([c["key"] for c in sp["categories"]], list(bos.COST_CATEGORIES))
        self.assertAlmostEqual(sp["total"], sum(c["eur"] for c in sp["categories"]), places=2)
        cats = {c["key"]: c for c in sp["categories"]}
        self.assertFalse(cats["groceries"]["est"])
        self.assertTrue(cats["tobacco"]["est"])
        self.assertEqual(sp["unknown"], 0)

    def test_settings_helpers(self):
        today = dt.date(2026, 10, 13)  # a Tuesday
        self.assertEqual(bos.extract_focus("# R\n## Fokus der Woche\n- **Eins** tun\n- zwei\n"), "**Eins** tun")
        self.assertEqual(bos.extract_focus("## Focus\n\nOne paragraph\nwrapped.\n\n## Next"), "One paragraph wrapped.")
        self.assertEqual(bos.extract_focus("- Next week's focus: walk daily"), "walk daily")
        self.assertIsNone(bos.extract_focus("# nothing here"))
        self.assertEqual(bos._measure_due("weekly:tue", set(), today), {"status": "due"})
        self.assertEqual(bos._measure_due("weekly:tue", {dt.date(2026, 10, 9)}, today), {"status": "done"})
        self.assertIsNone(bos._measure_due("weekly:mon", set(), today))
        self.assertEqual(bos._measure_due("monthly:first-sun", set(), dt.date(2026, 10, 4)), {"status": "due"})
        self.assertIsNone(bos._measure_due("monthly:first-sun", set(), dt.date(2026, 10, 11)))
        self.assertEqual(bos._measure_due("2x-week", {dt.date(2026, 10, 12)}, today), {"status": "open", "count": 1, "of": 2})
        sat = {dt.date(2026, 10, 17): [{"kind": "run"}]}
        due, nxt = bos.training_due({"training": {"schedule": {"sat|sun": "endurance"}}}, sat, dt.date(2026, 10, 18))
        self.assertEqual(due[0]["done_day"], "2026-10-17")  # either-day rule: Saturday counts for Sunday
        due, nxt = bos.training_due({"training": {"schedule": {"sat|sun": "endurance"}}}, {}, today)
        self.assertEqual((due, nxt), ([], {"day": "2026-10-17", "what": "endurance"}))
        phases = bos.settings_phases({"phases": [{"id": "b", "from": "2026-10-01"}, {"id": "x", "from": "bad"}]})
        self.assertEqual([p["id"] for p in phases], ["b"])
        self.assertEqual(bos.phase_json(phases[0], today)["of"], None)

    def test_empty_instance_gives_valid_empty_structure(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        for period in ("14", "all"):
            d = bos.dashboard_data(bos.Ctx(empty, self.data, DEMO_TODAY), period)
            self.assert_shape(d)
            self.assertEqual(d["period"]["days_logged"], 0)
            self.assertEqual(len(d["days"]), 14)
            self.assertTrue(all(r["weight_kg"] is None and r["substance_n"] == 0 for r in d["days"]))
            T = d["tabs"]
            for tab, k in (("substances", "use_times"), ("sleep", "vs_last_use"), ("sleep", "nights"),
                           ("kitchen", "pantry"), ("kitchen", "cookbook"), ("kitchen", "waste"),
                           ("kitchen", "purchases"), ("substances", "trigger_order"), ("body", "labs"),
                           ("journal", "reviews"), ("journal", "timeline"), ("journal", "decisions"),
                           ("training", "next_goals"), ("nutrition", "protein_sources")):
                self.assertEqual(T[tab][k], [], (tab, k))
            for tab, k in (("today", "phase"), ("today", "focus"), ("today", "next_decision"), ("body", "corridor"),
                           ("substances", "plan_b"), ("substances", "baseline"), ("kitchen", "shopping_list")):
                self.assertIsNone(T[tab][k], (tab, k))
            self.assertEqual(T["training"]["lifts"], {"exercises": {}, "others": []})
            self.assertFalse(T["substances"]["active"])
            self.assertEqual(T["today"]["spend_month"]["total"], 0)
            self.assertEqual([c["key"] for c in T["today"]["checklist"]], ["weight", "sleep", "meals", "checkin"])
            self.assertEqual(d["language"], "en")

    def test_review_files_whitelist_and_traversal(self):
        rdir = os.path.join(self.me, "reviews")
        self.assertEqual(bos.review_files(self.me), ["2026-W41.md", "2026-W40.md", "2026-09.md"])
        with open(os.path.join(self.me, "secret.md"), "w") as f:
            f.write("secret")
        with open(os.path.join(rdir, "notes.md"), "w") as f:
            f.write("not a review")
        os.symlink(os.path.join(self.me, "secret.md"), os.path.join(rdir, "2026-W01.md"))
        self.assertIn("Fokus der Woche", bos.review_text(self.me, "2026-W40.md"))
        for bad in ("../secret.md", "notes.md", "2026-W41.md/..", "..%2Fsecret.md", "2026-W41.MD", "",
                    "/etc/passwd", "2026-W1.md", "2026-W41.md\x00", "2026-W01.md"):
            self.assertIsNone(bos.review_text(self.me, bad), bad)
        self.assertNotIn("2026-W01.md", bos.review_files(self.me))  # symlink escaping reviews/ is not listed

    def test_server_serves_static_and_api_only(self):
        import http.client
        import threading
        srv = bos.make_dashboard_server(bos.Ctx(self.me, self.data, DEMO_TODAY), port=0, today=DEMO_TODAY)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        port = srv.server_address[1]
        self.assertEqual(srv.server_address[0], "127.0.0.1")

        def get(path, host=None):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("GET", path, headers={"Host": host} if host else {})
            r = c.getresponse()
            body = r.read()
            c.close()
            return r.status, r.getheader("Content-Type") or "", body

        try:
            code, ctype, body = get("/")
            self.assertEqual(code, 200)
            self.assertIn("text/html", ctype)
            self.assertIn(b"echarts.min.js", body)
            self.assertNotIn(b"http://", body.replace(b"http://www.w3.org", b""))  # no external resources
            self.assertNotIn(b"https://", body)
            code, ctype, body = get("/api/data?days=14")
            self.assertEqual(code, 200)
            self.assertIn("application/json", ctype)
            d = json.loads(body)
            self.assertEqual(d["period"]["days"], 14)
            self.assertEqual(d["today"], DEMO_TODAY)
            self.assertEqual(get("/api/data")[0], 200)  # default period
            self.assertEqual(get("/api/data?days=evil")[0], 400)
            for bad in ("/../tools/bos.py", "/%2e%2e/bos.py", "/..%2fbos.py", "/vendor/../../bos.py",
                        "/.hidden", "/nope.js", "/vendor/ECHARTS-LICENSE"):
                self.assertIn(get(bad)[0], (403, 404), bad)
            self.assertEqual(get("/app.js")[0], 200)
            self.assertEqual(get("/markdown.js")[0], 200)
            code, ctype, body = get("/api/review?file=2026-W41.md")
            self.assertEqual((code, json.loads(body)["file"]), (200, "2026-W41.md"))
            self.assertIn("Next week's focus", json.loads(body)["text"])
            for bad in ("../settings.json", "..%2Fsettings.json", "2026-W41.md%2F..", "%2E%2E/profile.md",
                        "notes.md", "", "2026-W41.md%00"):
                self.assertEqual(get("/api/review?file=" + bad)[0], 400, bad)
            self.assertEqual(get("/api/review")[0], 400)
            self.assertEqual(get("/api/review?file=2020-W01.md")[0], 404)
            self.assertEqual(get("/api/review?file=2026-W41.md", host="evil.example:%d" % port)[0], 403)
            self.assertEqual(get("/vendor/echarts.min.js")[0], 200)
            self.assertEqual(get("/api/data?days=14", host="evil.example:%d" % port)[0], 403)  # DNS rebinding
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("POST", "/api/data", body=b"{}")
            self.assertNotEqual(c.getresponse().status, 200)  # read-only
            c.close()
        finally:
            srv.shutdown()
            srv.server_close()

    def test_vendored_echarts_matches_recorded_hash(self):
        vendor = os.path.join(ROOT, "tools", "dashboard", "vendor")
        with open(os.path.join(vendor, "README.md")) as f:
            readme = f.read()
        with open(os.path.join(vendor, "echarts.min.js"), "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        self.assertIn(digest, readme)
        for name in ("ECHARTS-LICENSE", "ECHARTS-NOTICE"):
            self.assertTrue(os.path.exists(os.path.join(vendor, name)))


class TestUpcomingPhase(unittest.TestCase):
    def test_banner_shows_next_phase_before_plan_starts(self):
        phases = bos.settings_phases({"phases": [{"id": "baseline", "name": "Baseline", "from": "2026-10-14", "to": "2026-10-27"}]})
        today = dt.date(2026, 10, 13)
        self.assertIsNone(bos.current_phase(phases, today))
        up = bos.upcoming_phase_json(phases, today)
        self.assertTrue(up["upcoming"])
        self.assertEqual(up["starts_in"], 1)
        self.assertIsNone(bos.upcoming_phase_json(phases, dt.date(2026, 10, 14)))


class TestSync(unittest.TestCase):
    def test_home_remote_classification(self):
        home = ["fabian@faberry.local:body-os/me", "ssh://pi@192.168.178.63/x", "/srv/x", "nas.fritz.box:x",
                "pi@10.0.0.5:x"]
        away = ["git@github.com:a/b.git", "https://github.com/a/b", "ssh://me@example.com/x", "pi@8.8.8.8:x"]
        for u in home:
            self.assertTrue(bos.is_home_remote(u), u)
        for u in away:
            self.assertFalse(bos.is_home_remote(u), u)
        self.assertTrue(bos.is_home_remote("me@myserver.example:x", ["myserver.example"]))

    def test_sync_merges_concurrent_jsonl_appends(self):
        tmp = tempfile.mkdtemp(prefix="bos-sync-")
        try:
            g = lambda cwd, *a: subprocess.run(["git"] + list(a), cwd=cwd, capture_output=True, text=True)
            server, me = os.path.join(tmp, "server"), os.path.join(tmp, "me")
            os.makedirs(os.path.join(me, "log"))
            for repo in (me,):
                g(repo, "init", "-q", "-b", "main")
            for repo in (me,):
                g(repo, "config", "user.email", "t@example.invalid")
                g(repo, "config", "user.name", "t")
            line = lambda n: '{"id": "w%d", "ts": "2026-10-1%dT08:00:00+02:00", "type": "weight", "kg": 70}\n' % (n, n)
            with open(os.path.join(me, "log", "a.jsonl"), "w") as f:
                f.write(line(1))
            g(me, "add", "-A"); g(me, "commit", "-qm", "init")
            g(tmp, "clone", "-q", me, server)
            g(server, "config", "receive.denyCurrentBranch", "updateInstead")
            g(server, "config", "user.email", "t@example.invalid"); g(server, "config", "user.name", "t")
            g(me, "remote", "add", "home", server)
            ctx = bos.Ctx(me, os.path.join(tmp, "data"))
            self.assertEqual(bos.cmd_sync(ctx, argparse.Namespace(push_only=False, pull_only=False)), 0)
            # concurrent appends on both sides
            with open(os.path.join(server, "log", "a.jsonl"), "a") as f:
                f.write(line(2))
            g(server, "commit", "-qam", "server side")
            with open(os.path.join(me, "log", "a.jsonl"), "a") as f:
                f.write(line(3))
            self.assertEqual(bos.cmd_sync(ctx, argparse.Namespace(push_only=False, pull_only=False)), 0)
            with open(os.path.join(server, "log", "a.jsonl")) as f:
                ids = [json.loads(l)["id"] for l in f if l.strip()]
            self.assertEqual(sorted(ids), ["w1", "w2", "w3"])
            # a non-home remote is refused
            g(me, "remote", "set-url", "home", "git@github.com:someone/leak.git")
            self.assertEqual(bos.cmd_sync(ctx, argparse.Namespace(push_only=False, pull_only=False)), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestReadiness(TempMe):
    def test_joint_tobacco_default_and_kinds(self):
        with open(os.path.join(self.me, "settings.json")) as f:
            st = json.load(f)
        st.setdefault("substances", {})["joint_default_tobacco"] = True
        with open(os.path.join(self.me, "settings.json"), "w") as f:
            json.dump(st, f)
        code, out, _ = self.bos("log", '[{"type": "substance", "kind": "joint", "trigger": "break"},'
                                       ' {"type": "substance", "kind": "joint", "tobacco": false},'
                                       ' {"type": "substance", "kind": "cigarette"},'
                                       ' {"type": "substance", "kind": "cannabis_vape"}]', "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual([json.loads(l)["tobacco"] for l in out.splitlines() if l.startswith("{")], [True, False, True, False])

    def test_questionnaire_and_supply_events(self):
        code, _, err = self.bos("log", '[{"type": "questionnaire", "name": "phq4", "items": [1,0,1,1], "score": 3},'
                                       ' {"type": "supply", "item": "tobacco", "action": "open", "g": 30, "ts": "2026-10-01T10:00"},'
                                       ' {"type": "supply", "item": "tobacco", "action": "empty", "ts": "2026-10-11T10:00"}]')
        self.assertEqual(code, 0, err)
        code, out, _ = self.bos("summary", "--days", "14")
        self.assertIn("tobacco measured: 30 g in 10.0 days = 3.00 g/day", out)
        self.assertIn("questionnaires: phq4 3", out)
        self.assertNotEqual(self.bos("log", '{"type": "supply", "item": "tobacco", "action": "bought"}')[0], 0)

    def test_duplicate_ids_count_once(self):
        line = '{"id": "w-dup", "ts": "2026-10-12T07:00:00+02:00", "type": "weight", "kg": 99}\n'
        path = os.path.join(self.me, "log", "2026", "2026-10.jsonl")
        with open(path, "a") as f:
            f.write(line)
            f.write(line.replace("99", "98"))
        ctx = bos.Ctx(self.me, self.data, DEMO_TODAY)
        dups = [e for e in ctx.log_events() if e.get("id") == "w-dup"]
        self.assertEqual([e["kg"] for e in dups], [98])

    def test_summary_has_first_use_column(self):
        code, out, _ = self.bos("summary", "--days", "3")
        self.assertIn("first", out.splitlines()[1])


class TestHooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-hook-")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        shutil.copytree(os.path.join(ROOT, ".githooks"), os.path.join(self.repo, ".githooks"))
        self.git("init", "-q")
        self.git("config", "core.hooksPath", ".githooks")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")
        self.write("README.md", "engine\n")
        self.git("add", "README.md", ".githooks")
        self.assertEqual(self.git("commit", "-qm", "init").returncode, 0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args, cwd=None):
        return subprocess.run(["git"] + list(args), cwd=cwd or self.repo, capture_output=True, text=True)

    def write(self, rel, text):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def test_pre_commit_blocks_private_paths(self):
        for rel in ("me/log/2026/2026-10.jsonl", "data/body-os.sqlite", ".env.local"):
            self.write(rel, "x\n")
            self.git("add", "-f", rel)
            r = self.git("commit", "-qm", "leak")
            self.assertNotEqual(r.returncode, 0, rel)
            self.assertIn("refusing to commit", r.stderr)
            self.assertIn(rel, r.stderr)
            self.git("rm", "-q", "--cached", rel)

    def test_pre_commit_blocks_non_ascii_and_uppercase_paths(self):
        for rel in ("me/doctor/Blutbild-M\u00e4rz.md", "sub/\u00e4.jsonl"):
            self.write(rel, '{"ts": "2026", "type": "weight"}\n')
            self.git("add", "-f", rel)
            r = self.git("commit", "-qm", "leak")
            self.assertNotEqual(r.returncode, 0, rel)
            self.git("rm", "-q", "--cached", rel)

    def test_pre_push_blocks_merge_and_no_verify_commits(self):
        bare = os.path.join(self.tmp, "remote2.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        self.git("remote", "add", "o2", bare)
        self.assertEqual(self.git("push", "-q", "o2", "HEAD:refs/heads/main").returncode, 0)
        base = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.git("checkout", "-qb", "side")
        self.write("side.txt", "s\n")
        self.git("add", "side.txt")
        self.git("commit", "-qm", "side")
        self.git("checkout", "-q", base)
        self.write("m.txt", "m\n")
        self.git("add", "m.txt")
        self.git("commit", "-qm", "m")
        self.git("merge", "-q", "--no-commit", "side")
        self.write("me/x.md", "secret\n")
        self.git("add", "-f", "me/x.md")
        self.git("commit", "-q", "-n", "-m", "merge")
        r = self.git("push", "o2", "HEAD:refs/heads/main")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refusing to push", r.stderr)

    def test_pre_commit_blocks_log_lines_outside_examples(self):
        line = '{"id": "w", "ts": "2026-10-01T08:00:00+02:00", "type": "weight", "kg": 70}\n'
        self.write("tests/fixture.jsonl", line)
        self.git("add", "tests/fixture.jsonl")
        self.assertNotEqual(self.git("commit", "-qm", "fixture").returncode, 0)
        self.git("rm", "-q", "--cached", "tests/fixture.jsonl")
        self.write("examples/demo-me/log/2026/2026-10.jsonl", line)
        self.write("tools/x.py", "print(1)\n")
        self.git("add", "examples", "tools")
        self.assertEqual(self.git("commit", "-qm", "ok").returncode, 0)

    def test_pre_push_blocks_private_paths(self):
        bare = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        self.git("remote", "add", "origin", bare)
        self.assertEqual(self.git("push", "-q", "origin", "HEAD:refs/heads/main").returncode, 0)
        self.write("me/profile.md", "private\n")
        self.git("add", "-f", "me/profile.md")
        self.assertEqual(self.git("commit", "--no-verify", "-qm", "sneak").returncode, 0)
        r = self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("me/profile.md", r.stderr)

    def test_pre_commit_blocks_people_and_household(self):
        for rel in ("people/louise/settings.json", "household/household.json", "Household/server.json",
                    "PEOPLE/x/profile.md"):
            self.write(rel, "{}\n")
            self.git("add", "-f", rel)
            r = self.git("commit", "-qm", "leak")
            self.assertNotEqual(r.returncode, 0, rel)
            self.assertIn("refusing to commit", r.stderr)
            self.git("rm", "-q", "--cached", rel)
        self.write("examples/demo-household/people/sam/settings.json", "{}\n")
        self.git("add", "examples")
        self.assertEqual(self.git("commit", "-qm", "synthetic demo is fine").returncode, 0)


def make_foods_fixture(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE foods (food_id TEXT PRIMARY KEY, name_de TEXT, name_en TEXT, category TEXT, kcal REAL,
          protein_g REAL, fat_g REAL, carbs_g REAL, fiber_g REAL, sugar_g REAL, salt_g REAL, note TEXT,
          search_key TEXT, source TEXT);
        CREATE TABLE nutrients (food_id TEXT, component TEXT, value REAL, unit TEXT, status TEXT, method TEXT);
    """)
    rows = [("bls:X000001", "Hafer Flocken", "Oat flakes", "C", 350, 13.0, 7.0, 58.0, 10.0, 1.0, 0.0),
            ("bls:X000002", "Hähnchen Brust roh", "Chicken breast raw", "U", 110, 23.0, 2.0, 0.0, None, 0.0, 0.2)]
    for r in rows:
        con.execute("INSERT INTO foods VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,?,'test')",
                    r + (bos.norm_name(r[1]) + " " + bos.norm_name(r[2]),))
    con.execute("INSERT INTO nutrients VALUES ('bls:X000002', 'FIBT', NULL, 'g', 'missing', NULL)")
    con.commit()
    con.close()


class TestFood(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-food-")
        make_foods_fixture(os.path.join(self.tmp, "foods.sqlite"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_calc_sums_and_reports_missing(self):
        code, out, _ = run("--data", self.tmp, "food", "calc",
                           '[{"food_id": "bls:X000001", "g": 50}, {"food_id": "X000002", "g": 200}]', "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertAlmostEqual(res["totals"]["kcal"], 175 + 220)
        self.assertAlmostEqual(res["totals"]["protein_g"], 6.5 + 46)
        self.assertAlmostEqual(res["totals"]["fiber_g"], 5.0)  # chicken fiber missing, not counted as 0
        self.assertEqual(res["missing"], [{"food_id": "bls:X000002", "name": "Hähnchen Brust roh",
                                           "nutrient": "fiber_g", "status": "missing"}])
        code, out, _ = run("--data", self.tmp, "food", "calc", '[{"food_id": "bls:NOPE", "g": 10}]')
        self.assertEqual(code, 1)
        self.assertIn("unknown food_id: bls:NOPE", out)

    def test_search_is_space_and_diacritic_insensitive(self):
        code, out, _ = run("--data", self.tmp, "food", "search", "Haferflocken")
        self.assertEqual(code, 0)
        self.assertIn("bls:X000001", out)
        code, out, _ = run("--data", self.tmp, "food", "search", "hahnchen")
        self.assertIn("bls:X000002", out)


def _cell_ref(col, row):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return "%s%d" % (s, row)


def make_bls_zip(path):
    """Tiny synthetic archive with the BLS 4.0 data-workbook layout (inline strings)."""
    comps = [("ENERCC", "Energie", "kcal"), ("PROT625", "Protein", "g"), ("FAT", "Fett", "g"),
             ("CHO", "Kohlenhydrate", "g"), ("FIBT", "Ballaststoffe", "g"), ("SUGAR", "Zucker", "g"),
             ("NACL", "Salz", "g")]
    header = ["BLS Code", "Lebensmittelbezeichnung", "Food name"]
    for code, name, unit in comps:
        header += ["%s %s [%s/100g]" % (code, name, unit), code + " Datenherkunft", code + " Referenz"]
    header.append("Hinweis")
    foods = [["T100001", "Testbrot", "Test bread", 250, 9.5, 1.2, 48, "-", "TR", 1.1, "Hinweis A"],
             ["T100002", "Testöl", "Test oil", 900, 0, 100, 0, 0, "<LOD", "", ""]]

    def cell(col, row, v):
        if isinstance(v, (int, float)):
            return '<c r="%s"><v>%s</v></c>' % (_cell_ref(col, row), v)
        if v == "":
            return ""
        return '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (_cell_ref(col, row), escape(v))
    rows = ['<row r="1">%s</row>' % "".join(cell(i + 1, 1, h) for i, h in enumerate(header))]
    for rn, f in enumerate(foods, 2):
        cells = [cell(1, rn, f[0]), cell(2, rn, f[1]), cell(3, rn, f[2])]
        for i, v in enumerate(f[3:10]):
            cells += [cell(4 + 3 * i, rn, v), cell(5 + 3 * i, rn, "Analyse")]
        cells.append(cell(len(header), rn, f[10]))
        rows.append('<row r="%d">%s</row>' % (rn, "".join(cells)))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    xbuf = io.BytesIO()
    with zipfile.ZipFile(xbuf, "w") as x:
        x.writestr("xl/workbook.xml", '<workbook %s xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                   'relationships"><sheets><sheet name="T" sheetId="1" r:id="rId1"/></sheets></workbook>' % ns)
        x.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
                   '2006/relationships"><Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
                   '</Relationships>')
        x.writestr("xl/worksheets/sheet1.xml", "<worksheet %s><sheetData>%s</sheetData></worksheet>" % (ns, "".join(rows)))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("BLS_9_9_2099_DE/BLS_9_9_Daten_2099_DE.xlsx", xbuf.getvalue())


class TestFoodsImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-bls-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_synthetic_workbook(self):
        src = os.path.join(self.tmp, "mini.zip")
        make_bls_zip(src)
        out = os.path.join(self.tmp, "foods.sqlite")
        with contextlib.redirect_stdout(io.StringIO()):
            st = bos.import_bls(src, out, log=lambda *a: None)
        self.assertEqual(st["foods"], 2)
        con = sqlite3.connect(out)
        r = con.execute("SELECT kcal, protein_g, fiber_g, sugar_g, salt_g, note FROM foods WHERE food_id = 'bls:T100001'").fetchone()
        self.assertEqual(r, (250, 9.5, None, None, 1.1, "Hinweis A"))  # '-' missing, 'TR' trace -> NULL, not 0
        status = dict(con.execute("SELECT component, status FROM nutrients WHERE food_id = 'bls:T100002'").fetchall())
        self.assertEqual(status, {"ENERCC": "numeric", "PROT625": "zero", "FAT": "numeric", "CHO": "zero",
                                  "FIBT": "zero", "SUGAR": "below_lod", "NACL": "missing"})
        self.assertEqual(con.execute("SELECT status FROM nutrients WHERE food_id='bls:T100001' AND component='SUGAR'")
                         .fetchone()[0], "trace")
        self.assertIn("doi:10.25826", dict(con.execute("SELECT * FROM meta"))["attribution"])

    @unittest.skipUnless(os.path.exists(BLS_ZIP), "BLS 4.0 archive not present in data/sources/")
    def test_real_bls_archive(self):
        out = os.path.join(self.tmp, "foods.sqlite")
        st = bos.import_bls(BLS_ZIP, out, log=lambda *a: None)
        self.assertEqual(st["foods"], 7140)
        self.assertEqual(st["components"], 138)
        self.assertEqual(st["sha256"], bos.BLS_SHA256)
        # marker counts from the known release (same as Supper-Board's regression numbers)
        self.assertEqual(st["status_counts"], {"numeric": 656320, "zero": 213181, "missing": 110083 + 59,
                                               "below_loq": 746, "below_lod": 2733, "below_lod_or_loq": 392,
                                               "trace": 1806})
        con = sqlite3.connect(out)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM nutrients").fetchone()[0], 7140 * 138)
        name, kcal = con.execute("SELECT name_de, kcal FROM foods WHERE food_id = 'bls:C133000'").fetchone()
        self.assertEqual((name, kcal), ("Hafer Flocken", 348))


# --------------------------------------------------------------------------------------------
# Household mode, profiles, LAN server, PWA, service
# --------------------------------------------------------------------------------------------

class TempHousehold(unittest.TestCase):
    """A temp copy of examples/demo-household: base/household + base/people/{alex,sam,robin}
    (alex and sam consented; robin has not done the interview yet)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-hh-")
        self.base = os.path.join(self.tmp, "base")
        shutil.copytree(DEMO_HH, self.base)
        self.hh = os.path.join(self.base, "household")
        self.data = os.path.join(self.tmp, "data")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bos(self, *argv, profile=None, today=DEMO_TODAY):
        args = ["--household", self.hh, "--data", self.data, "--today", today]
        if profile:
            args += ["--profile", profile]
        return run(*(args + list(argv)))

    def ctx(self, profile=None):
        return bos.Ctx(None, self.data, DEMO_TODAY, self.hh, profile)


class TestHouseholdPaths(TempHousehold):
    def test_single_user_paths_unchanged(self):
        me = os.path.join(self.base, "people", "alex")
        c = bos.Ctx(me, self.data, DEMO_TODAY)  # explicit --me without --household: single-user
        self.assertIsNone(c.household)
        self.assertEqual(c.pantry_path, os.path.join(me, "pantry", "pantry.jsonl"))
        self.assertEqual(c.cookbook_path, os.path.join(me, "recipes", "cookbook.jsonl"))
        self.assertEqual(c.profile_id, "me")
        self.assertTrue(c.consent)
        self.assertEqual([m["id"] for m in c.members()], ["me"])
        with self.assertRaises(bos.BosError):
            bos.Ctx(me, self.data, DEMO_TODAY, None, "alex")

    def test_household_resolution_and_shared_kitchen(self):
        c = self.ctx()
        self.assertEqual(c.profile_id, "alex")  # default_member
        self.assertEqual(os.path.realpath(c.me), os.path.realpath(os.path.join(self.base, "people", "alex")))
        self.assertEqual(c.pantry_path, os.path.join(self.hh, "pantry", "pantry.jsonl"))
        self.assertEqual(c.cookbook_path, os.path.join(self.hh, "recipes", "cookbook.jsonl"))
        self.assertEqual(c.shopping_list_path, os.path.join(self.hh, "pantry", "shopping-list.md"))
        self.assertEqual(c.settings["household"]["portions_default"], 2)   # shared key from household
        self.assertEqual(c.settings["goals"]["protein_g_per_kg"], [1.6, 2.0])  # personal key from member
        self.assertEqual(c.settings["costs"]["tobacco_eur_per_g"], 0.35)   # costs merged, not replaced
        robin = self.ctx("robin")
        self.assertFalse(robin.consent)
        self.assertTrue(self.ctx("sam").consent)
        self.assertEqual(robin.pantry_path, c.pantry_path)
        with self.assertRaises(bos.BosError):
            self.ctx("nobody")
        # same pantry for both members via the CLI
        for p in ("alex", "sam", "robin"):
            code, out, _ = self.bos("pantry", "--json", profile=p)
            self.assertEqual(code, 0)
            self.assertEqual(len(json.loads(out)), 14)

    def test_fallback_to_instance_files_and_default_without_default_member(self):
        os.remove(os.path.join(self.hh, "recipes", "cookbook.jsonl"))
        mine = os.path.join(self.base, "people", "alex", "recipes", "cookbook.jsonl")
        os.makedirs(os.path.dirname(mine))
        shutil.copy(os.path.join(DEMO, "recipes", "cookbook.jsonl"), mine)
        self.assertEqual(self.ctx().cookbook_path, mine)
        hj = os.path.join(self.hh, "household.json")
        with open(hj) as f:
            hh = json.load(f)
        hh["default_member"] = None
        with open(hj, "w") as f:
            json.dump(hh, f)
        c = self.ctx()  # no default member, nobody at me/ -> base/me, no member
        self.assertIsNone(c.member)
        self.assertEqual(c.me, os.path.join(self.base, "me"))

    def test_invalid_household_json_is_reported(self):
        hj = os.path.join(self.hh, "household.json")
        for bad in ({"members": [{"id": "a", "name": "A", "color": "pink", "path": "people/a", "consent": True}]},
                    {"members": [{"id": "a", "name": "A", "color": "blue", "path": "../a", "consent": True}]},
                    {"members": [{"id": "A b", "name": "A", "color": "blue", "path": "people/a", "consent": True}]},
                    {"members": [{"id": "a", "name": "A", "color": "blue", "path": "household", "consent": True}]},
                    {"members": [], "default_member": "x"}):
            with open(hj, "w") as f:
                json.dump(bad, f)
            with self.assertRaises(bos.BosError):
                self.ctx()

    def test_dashboard_data_for_member_without_consent_has_no_personal_data(self):
        d = bos.dashboard_data(self.ctx("robin"), "30")
        self.assertEqual(d["profile"]["id"], "robin")
        self.assertFalse(d["profile"]["consent"])
        self.assertEqual(d["period"]["days_logged"], 0)
        self.assertEqual(d["tabs"]["journal"]["reviews"], [])
        self.assertTrue(d["tabs"]["kitchen"]["pantry"])
        self.assertTrue(d["tabs"]["kitchen"]["shared"])
        self.assertEqual([m["id"] for m in d["household"]["members"]], ["alex", "sam", "robin"])
        a = bos.dashboard_data(self.ctx("alex"), "30")
        self.assertGreater(a["period"]["days_logged"], 10)
        self.assertEqual(a["tabs"]["kitchen"]["pantry"], d["tabs"]["kitchen"]["pantry"])


FORBIDDEN_COMPARE = ("kg", "weight", "kcal", "waist", "bp", "lab", "sys", "dia")


def _walk(obj, keys, nums):
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k).lower())
            _walk(v, keys, nums)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, keys, nums)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        nums.add(round(float(obj), 2))


class TestCompare(TempHousehold):
    def assert_no_body_numbers(self, data, weights):
        keys, nums = set(), set()
        _walk(data, keys, nums)
        bad = [k for k in keys for f in FORBIDDEN_COMPARE if f in re.split(r"[_\W]+", k)]
        self.assertEqual(bad, [])
        for w in weights:  # whole-number weights could equal a percentage by chance; fractional ones cannot
            if float(w) != int(w):
                self.assertNotIn(round(float(w), 2), nums)
        self.assertNotIn('"kg"', json.dumps(data))

    def member(self, pid, settings, events, consent=True):
        d = os.path.join(self.base, "people", pid)
        os.makedirs(os.path.join(d, "log", "2026"), exist_ok=True)
        bos.write_json_file(os.path.join(d, "settings.json"), dict({"timezone": "Europe/Berlin"}, **settings))
        with open(os.path.join(d, "log", "2026", "2026-10.jsonl"), "w") as f:
            for i, e in enumerate(events):
                f.write(json.dumps(dict(e, id="%s-%d" % (e["type"], i))) + "\n")
        return {"id": pid, "name": pid.upper() + " Test", "color": "blue", "path": "people/" + pid, "consent": consent}

    @staticmethod
    def days_events(sleep_h, water_ml, weight, protein, trainings, checkin=None, tobacco=0):
        evs = []
        for i in range(7):  # 2026-10-07 .. 2026-10-13
            d = dt.date(2026, 10, 7) + dt.timedelta(days=i)
            bed = dt.datetime.combine(d, dt.time(7, 0)) - dt.timedelta(hours=sleep_h)
            day = d.isoformat()
            evs += [{"type": "sleep", "ts": day + "T07:00:00+02:00", "bed": bed.strftime("%Y-%m-%dT%H:%M:00+02:00"),
                     "wake": day + "T07:00:00+02:00", "quality": 4},
                    {"type": "weight", "ts": day + "T07:10:00+02:00", "kg": weight},
                    {"type": "meal", "ts": day + "T12:00:00+02:00", "slot": "lunch", "kcal": 711, "protein_g": protein / 2},
                    {"type": "meal", "ts": day + "T19:00:00+02:00", "slot": "dinner", "kcal": 733, "protein_g": protein / 2},
                    {"type": "drink", "ts": day + "T10:00:00+02:00", "kind": "water", "ml": water_ml}]
            if checkin:
                evs.append(dict({"type": "checkin", "ts": day + "T21:00:00+02:00"}, **checkin))
            for k in range(tobacco):
                evs.append({"type": "substance", "ts": day + "T1%d:00:00+02:00" % (k % 10), "kind": "cigarette", "tobacco": True})
        for day in trainings:
            evs.append({"type": "training", "ts": day + "T18:00:00+02:00", "kind": "run", "dur_min": 30})
        return evs

    def test_demo_household(self):
        d = bos.compare_data(self.ctx("sam"), "14")  # same result whoever asks
        self.assertEqual([m["id"] for m in d["members"]], ["alex", "sam"])
        self.assertEqual([(x["id"], x["reason"]) for x in d["excluded"]], [("robin", "no_consent")])
        self.assertEqual([g["id"] for g in d["groups"]],
                         ["consistency", "training", "sleep", "hydration", "protein", "wellbeing"])
        self.assertIn({"key": "all_must_share", "group": "substances"}, d["notes"])  # alex shares it, sam not
        self.assertEqual([g["id"] for g in d["week"]["groups"]], [g["id"] for g in d["groups"]])
        self.assertEqual([m["id"] for m in d["trends"]["metrics"]], ["plan_pct", "sleep_h", "complete_days_pct"])
        for g in d["groups"]:
            self.assertEqual(g["members"], ["alex", "sam"])
            for m in g["metrics"]:
                self.assertTrue(set(m["values"]) <= {"alex", "sam"})
                self.assertIn(m["leader"], (None, "alex", "sam"))
                for x in m["values"].values():
                    self.assertTrue(bos.is_int(x["n"]) and x["n"] >= 0)
        sleep = {m["id"]: m for m in next(g for g in d["groups"] if g["id"] == "sleep")["metrics"]}
        self.assertEqual(sleep["bedtime_sd_min"]["direction"], "lower")
        self.assertEqual(sleep["bedtime_sd_min"]["leader"], "sam")  # demo: sam keeps a regular bedtime
        weights = [e["kg"] for pid in ("alex", "sam") for e in bos.Ctx(None, self.data, DEMO_TODAY, self.hh, pid).log_events()
                   if e.get("type") == "weight"]
        self.assertTrue(weights)
        self.assert_no_body_numbers(d, weights)
        with self.assertRaises(bos.BosError):
            bos.compare_data(self.ctx(), "7")

    def test_leaders_ties_consent_and_opt_in(self):
        a = self.member("aa", {"training": {"sessions_per_week": 2}, "nutrition": {"targets": {"protein_g": 100}},
                               "phases": [{"id": "baseline", "name": "B", "from": "2026-10-07", "to": "2026-10-09"}],
                               "compare": {"share": ["consistency", "training", "sleep", "hydration", "protein",
                                                     "wellbeing", "substances"]}},
                        self.days_events(8, 2000, 70.4, 80, ["2026-10-08", "2026-10-10", "2026-10-12"],
                                         {"energy": 4, "mood": 4, "stress": 2}))
        b = self.member("bb", {"training": {"sessions_per_week": 2}, "goals": {"protein_g_per_kg": [1.0, 1.0]}},
                        self.days_events(7, 2000, 90.6, 90, ["2026-10-09", "2026-10-12"]))  # no compare key: default share
        c = self.member("cc", {"compare": {"share": list(bos.COMPARE_GROUPS)}},
                        self.days_events(9, 3000, 66.6, 150, ["2026-10-08"]), consent=False)
        hh = {"schema": 1, "name": "T", "members": [a, b, c], "default_member": "aa"}
        bos.write_json_file(os.path.join(self.hh, "household.json"), hh)

        d = bos.compare_data(self.ctx(), "14")
        self.assertEqual([m["id"] for m in d["members"]], ["aa", "bb"])
        self.assertEqual(d["excluded"], [{"id": "cc", "name": "CC Test", "color": "blue", "initials": "CT",
                                          "reason": "no_consent"}])
        groups = {g["id"]: g for g in d["groups"]}
        self.assertNotIn("substances", groups)            # opt-in: only when every compared member shares it
        self.assertEqual(groups["wellbeing"]["members"], ["aa"])  # shown for the member who shares it ...
        self.assertTrue(all(m["leader"] is None for m in groups["wellbeing"]["metrics"]))  # ... never ranked alone
        met = {m["id"]: m for g in d["groups"] for m in g["metrics"]}
        self.assertNotIn("cc", json.dumps([m["values"] for m in met.values()]))
        self.assertEqual((met["sleep_h"]["values"]["aa"]["value"], met["sleep_h"]["values"]["bb"]["value"]), (8.0, 7.0))
        self.assertEqual(met["sleep_h"]["leader"], "aa")
        self.assertEqual(met["sleep_h"]["values"]["aa"]["n"], 7)
        self.assertEqual(met["water_l"]["values"]["aa"]["value"], met["water_l"]["values"]["bb"]["value"])
        self.assertIsNone(met["water_l"]["leader"])        # tie -> no lead
        self.assertEqual((met["plan_pct"]["values"]["aa"]["value"], met["plan_pct"]["values"]["bb"]["value"]), (150, 100))
        self.assertIsNone(met["plan_pct"]["leader"])       # both met their own plan -> no lead
        self.assertEqual((met["protein_pct"]["values"]["aa"]["value"], met["protein_pct"]["values"]["bb"]["value"]), (80, 99))
        self.assertEqual(met["protein_pct"]["leader"], "bb")  # relative to each own target, not grams
        # default checklist (weight, sleep, meals>=2, checkin): bb never logs a check-in
        self.assertEqual((met["complete_days_pct"]["values"]["aa"]["value"], met["complete_days_pct"]["values"]["bb"]["value"]),
                         (100, 0))
        self.assertEqual(met["complete_days_pct"]["values"]["aa"]["n"], 7)  # days before the first log don't count
        self.assertEqual((met["streak_current"]["values"]["aa"]["value"], met["streak_current"]["leader"]), (7, "aa"))
        self.assert_no_body_numbers(d, [70.4, 90.6, 66.6, 711, 733])

        st = os.path.join(self.base, "people", "bb", "settings.json")
        bos.write_json_file(st, dict(bos.read_json_file(st), compare={"share": ["sleep", "substances"]}))
        d = bos.compare_data(self.ctx(), "14")
        groups = {g["id"]: g for g in d["groups"]}
        self.assertEqual(groups["substances"]["members"], ["aa", "bb"])
        self.assertEqual(groups["training"]["members"], ["aa"])
        free = {m["id"]: m for m in groups["substances"]["metrics"]}["tobacco_free_days"]
        self.assertEqual((free["values"]["aa"]["value"], free["values"]["bb"]["value"], free["leader"]), (7, 7, None))

        # nutrition numbers off (SAFETY.md §2): protein is never shared; an empty share leaves the comparison
        bos.write_json_file(st, dict(bos.read_json_file(st), nutrition={"show_numbers": False},
                                     compare={"share": ["protein"]}))
        d = bos.compare_data(self.ctx(), "14")
        self.assertEqual([m["id"] for m in d["members"]], ["aa"])
        self.assertEqual([(x["id"], x["reason"]) for x in d["excluded"]], [("bb", "not_shared"), ("cc", "no_consent")])

    def test_single_user_has_no_comparison(self):
        self.assertIsNone(bos.compare_data(bos.Ctx(os.path.join(self.base, "people", "alex"), self.data, DEMO_TODAY), "14"))


class InitBase(unittest.TestCase):
    """A temp engine-like root with me/ (copy of demo-me) and household/ next to it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-hhinit-")
        self.me = os.path.join(self.tmp, "me")
        shutil.copytree(DEMO, self.me)
        self.hh = os.path.join(self.tmp, "household")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bos(self, *argv, profile=None):
        args = ["--household", self.hh, "--data", os.path.join(self.tmp, "data"), "--today", DEMO_TODAY]
        if profile:
            args += ["--profile", profile]
        return run(*(args + list(argv)))

    def read(self, *parts):
        with open(os.path.join(*parts), encoding="utf-8") as f:
            return f.read()



class TestConsentGate(TempHousehold):
    def test_explicit_me_of_a_member_still_enforces_consent(self):
        robin = os.path.join(self.base, "people", "robin")
        with mock.patch.object(bos, "DEFAULT_HOUSEHOLD", self.hh):
            c = bos.Ctx(robin, self.data, DEMO_TODAY)
            self.assertEqual((c.profile_id, c.consent), ("robin", False))
            code, _, err = run("--me", robin, "--data", self.data, "log", "--dry-run", '{"type": "weight", "kg": 60}')
            self.assertEqual(code, 2)
            self.assertIn("has not consented", err)
            other = os.path.join(self.tmp, "elsewhere")
            self.assertIsNone(bos.Ctx(other, self.data, DEMO_TODAY).household)  # unrelated --me: single-user

    def test_no_personal_settings_before_consent_and_no_member_no_writes(self):
        st = os.path.join(self.base, "people", "robin", "settings.json")
        with open(st) as f:
            d = json.load(f)
        d["goals"] = {"protein_g_per_kg": [1.6, 2.0]}
        d["phases"] = [{"id": "baseline", "name": "Secret", "from": "2026-10-01"}]
        with open(st, "w") as f:
            json.dump(d, f)
        data = bos.dashboard_data(self.ctx("robin"), "30")
        self.assertNotIn("Secret", json.dumps(data))
        self.assertIsNone(data["tabs"]["today"]["phase"])
        hj = os.path.join(self.hh, "household.json")
        with open(hj) as f:
            hh = json.load(f)
        hh["default_member"] = None
        with open(hj, "w") as f:
            json.dump(hh, f)
        code, _, err = self.bos("log", "--dry-run", '{"type": "weight", "kg": 60}')
        self.assertEqual(code, 2)
        self.assertIn("--profile", err)
        hh["members"].append({"id": "nested", "name": "N", "color": "red", "path": "people/sam/x", "consent": True})
        self.assertTrue(bos.household_errors(hh))


class TestHouseholdInit(InitBase):
    def test_init_needs_member_flags_when_me_exists(self):
        code, _, err = self.bos("household", "init")
        self.assertEqual(code, 2)
        self.assertIn("--member-id", err)
        self.assertFalse(os.path.exists(os.path.join(self.hh, "household.json")))

    def test_init_registers_me_and_moves_the_kitchen(self):
        originals = {rel: self.read(self.me, rel) for rel in bos.SHARED_FILES}
        code, out, err = self.bos("household", "init", "--name", "Test home", "--member-id", "alex",
                                  "--member-name", "Alex", "--color", "green")
        self.assertEqual(code, 0, err)
        hh = json.loads(self.read(self.hh, "household.json"))
        self.assertEqual(hh["name"], "Test home")
        self.assertEqual(hh["default_member"], "alex")
        self.assertEqual(hh["members"], [{"id": "alex", "name": "Alex", "color": "green", "path": "me", "consent": True}])
        for rel, text in originals.items():
            self.assertFalse(os.path.exists(os.path.join(self.me, rel)), rel)
            self.assertEqual(self.read(self.hh, rel), text, rel)  # content preserved
            self.assertIn("moved me/%s -> household/%s" % (rel, rel), out)
        self.assertTrue(bos.is_own_repo(self.hh))
        shared = json.loads(self.read(self.hh, "settings.json"))
        self.assertEqual(shared["pantry"]["grace_days"]["best_before"], 7)
        self.assertNotIn("goals", shared)  # personal settings stay personal
        c = bos.Ctx(None, None, DEMO_TODAY, self.hh)
        self.assertEqual((c.profile_id, c.me, c.consent), ("alex", self.me, True))
        self.assertEqual(c.pantry_path, os.path.join(self.hh, "pantry", "pantry.jsonl"))
        code, out, _ = self.bos("pantry", "--json")
        self.assertEqual(len(json.loads(out)), 14)
        code, out, _ = self.bos("household", "init")  # idempotent
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(self.read(self.hh, "household.json"))["members"]), 1)

    def test_init_never_overwrites_household_content(self):
        os.makedirs(os.path.join(self.hh, "recipes"))
        with open(os.path.join(self.hh, "recipes", "cookbook.jsonl"), "w") as f:
            f.write('{"id": "keep"}\n')
        os.makedirs(os.path.join(self.hh, "pantry"))
        open(os.path.join(self.hh, "pantry", "shopping-list.md"), "w").close()  # empty: may be replaced
        mine = self.read(self.me, "recipes", "cookbook.jsonl")
        code, out, _ = self.bos("household", "init", "--member-id", "alex", "--member-name", "Alex")
        self.assertEqual(code, 0)
        self.assertIn("kept  me/recipes/cookbook.jsonl", out)
        self.assertEqual(self.read(self.me, "recipes", "cookbook.jsonl"), mine)
        self.assertEqual(self.read(self.hh, "recipes", "cookbook.jsonl"), '{"id": "keep"}\n')
        self.assertTrue(self.read(self.hh, "pantry", "shopping-list.md"))
        code, out, _ = self.bos("doctor")
        self.assertIn("both household/recipes/cookbook.jsonl and me/recipes/cookbook.jsonl exist", out)


class TestProfiles(InitBase):
    def setUp(self):
        super().setUp()
        code, _, err = self.bos("household", "init", "--member-id", "alex", "--member-name", "Alex")
        self.assertEqual(code, 0, err)

    def test_add_creates_private_instance_without_consent(self):
        code, out, err = self.bos("profile", "add", "louise", "--name", "Louise", "--color", "violet")
        self.assertEqual(code, 0, err)
        inst = os.path.join(self.tmp, "people", "louise")
        st = json.loads(self.read(inst, "settings.json"))
        self.assertEqual((st["language"], st["modules"]), ("en", []))
        self.assertTrue(bos.is_own_repo(inst))
        self.assertEqual(bos.git(["remote"], inst).stdout.strip(), "")
        m = json.loads(self.read(self.hh, "household.json"))["members"][1]
        self.assertEqual(m, {"id": "louise", "name": "Louise", "color": "violet", "path": "people/louise", "consent": False})
        code, out, _ = self.bos("profile", "list")
        self.assertIn("louise", out)
        self.assertRegex(out, r"louise .*consent:no")
        code, out, _ = self.bos("profile", "list", "--json")
        self.assertEqual([x["initials"] for x in json.loads(out)["members"]], ["A", "L"])
        code, _, _ = self.bos("profile", "add", "louise", "--name", "Again")
        self.assertEqual(code, 2)
        code, _, _ = self.bos("profile", "add", "kim", "--name", "Kim", "--language", "de")
        self.assertEqual(json.loads(self.read(self.tmp, "people", "kim", "settings.json"))["language"], "de")
        code, _, _ = self.bos("profile", "add", "bad", "--name", "Bad", "--path", "../outside")
        self.assertEqual(code, 2)

    def test_no_events_for_member_without_consent(self):
        self.bos("profile", "add", "louise", "--name", "Louise")
        inst = os.path.join(self.tmp, "people", "louise")
        for cmd, ev in (("log", '{"type": "weight", "kg": 60}'),
                        ("pantry-log", '{"type": "purchase", "items": [{"name": "milk", "qty": 1, "unit": "pcs"}]}')):
            code, out, err = self.bos(cmd, ev, profile="louise")
            self.assertEqual(code, 2, cmd)
            self.assertIn("has not consented / not onboarded yet", err)
        self.assertEqual(os.listdir(os.path.join(inst, "log")), [])
        code, _, _ = self.bos("profile", "consent", "louise")
        self.assertEqual(code, 0)
        code, out, err = self.bos("log", '{"type": "weight", "kg": 60, "ts": "2026-10-13T08:00:00+02:00"}', profile="louise")
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.exists(os.path.join(inst, "log", "2026", "2026-10.jsonl")))
        self.bos("profile", "consent", "louise", "--revoke")
        self.assertEqual(self.bos("log", '{"type": "weight", "kg": 61}', profile="louise")[0], 2)

    def test_doctor_checks_every_member_and_household(self):
        self.bos("profile", "add", "louise", "--name", "Louise")
        bos.git(["init", "-q"], self.me)
        code, out, _ = self.bos("doctor")
        self.assertIn("household mode", out)
        self.assertIn("household/ is its own git repository", out)
        self.assertIn("household/ has no remote", out)
        self.assertIn("people/louise/ (louise, no consent yet) is its own git repository", out)
        self.assertIn("me/ (alex) has no remote", out)
        bos.git(["remote", "add", "origin", "https://example.invalid/x.git"], os.path.join(self.tmp, "people", "louise"))
        code, out, _ = self.bos("doctor")
        self.assertIn("!!! people/louise/ (louise, no consent yet) HAS A REMOTE OUTSIDE THE HOME NETWORK", out)

    def test_engine_ignores_people_and_household(self):
        for d in ("people/", "household/", "people/x/log/2026/2026-10.jsonl", "household/server.json"):
            self.assertEqual(bos.git(["check-ignore", "-q", d], ROOT).returncode, 0, d)
        self.assertNotEqual(bos.git(["check-ignore", "-q", "examples/demo-household/people/sam/settings.json"],
                                    ROOT).returncode, 0)


class TestLanServer(TempHousehold):
    def setUp(self):
        super().setUp()
        self.srv = bos.make_dashboard_server(self.ctx(), port=0, today=DEMO_TODAY)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        self.key_path = os.path.join(self.hh, "server.json")

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def get(self, path, host=None, cookie=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Host": host or "127.0.0.1:%d" % self.port}
        if cookie:
            headers["Cookie"] = cookie
        c.request("GET", path, headers=headers)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body

    def test_loopback_needs_no_key_and_serves_profiles(self):
        code, h, body = self.get("/api/profiles")
        self.assertEqual(code, 200)
        p = json.loads(body)
        self.assertEqual(p["default"], "alex")
        self.assertEqual([(m["id"], m["color"], m["consent"], m["initials"]) for m in p["members"]],
                         [("alex", "blue", True, "AD"), ("sam", "orange", True, "S"), ("robin", "aqua", False, "R")])
        self.assertNotIn("path", p["members"][0])  # folder layout stays on the server
        code, _, body = self.get("/api/data?profile=robin&days=14")
        d = json.loads(body)
        self.assertEqual((code, d["profile"]["id"], d["period"]["days_logged"]), (200, "robin", 0))
        self.assertTrue(d["tabs"]["kitchen"]["pantry"])
        code, _, body = self.get("/api/data?profile=alex&days=14")
        self.assertGreater(json.loads(body)["period"]["days_logged"], 0)
        self.assertEqual(json.loads(self.get("/api/data")[2])["profile"]["id"], "alex")
        self.assertEqual(self.get("/api/data?profile=nobody")[0], 404)
        self.assertEqual(self.get("/api/data?profile=../alex")[0], 404)
        self.assertEqual(self.get("/api/review?profile=alex&file=2026-W41.md")[0], 200)
        self.assertEqual(self.get("/api/review?profile=robin&file=2026-W41.md")[0], 404)
        self.assertEqual(self.get("/api/review?profile=nobody&file=2026-W41.md")[0], 404)
        self.assertEqual(self.get("/devices")[0], 200)
        code, _, body = self.get("/api/devices")
        self.assertEqual((code, json.loads(body)["key_set"], json.loads(body)["lan"]), (200, False, False))
        code, h, body = self.get("/manifest.webmanifest")
        self.assertEqual((code, h["content-type"]), (200, "application/manifest+json"))
        self.assertEqual(json.loads(body)["start_url"], "/")
        self.assertIn("manifest-src 'self'", h["content-security-policy"])
        self.assertNotIn("access-control-allow-origin", h)

    def test_other_clients_need_the_household_key(self):
        key = bos.ensure_server_key(self.key_path)
        self.assertEqual(os.stat(self.key_path).st_mode & 0o777, 0o600)
        self.assertEqual(bos.ensure_server_key(self.key_path), key)  # stable until rotated
        self.srv.is_local = lambda ip: False  # simulate a phone in the LAN
        for path in ("/", "/api/data?days=14", "/api/profiles", "/app.js", "/icons/icon-192.png",
                     "/manifest.webmanifest", "/?key=wrong", "/?key="):
            code, h, body = self.get(path)
            self.assertEqual(code, 401, path)
            self.assertNotIn(b"pantry", body)
        code, h, body = self.get("/")
        self.assertIn("bos.py devices --open", body.decode())
        self.assertIn("text/html", h["content-type"])
        code, h, _ = self.get("/?key=" + key)
        self.assertEqual((code, h["location"]), (302, "/"))
        cookie = h["set-cookie"]
        self.assertTrue(cookie.startswith("bos_key=%s;" % key))
        for attr in ("HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=34560000"):
            self.assertIn(attr, cookie)
        good = "bos_key=" + key
        self.assertEqual(self.get("/", cookie=good)[0], 200)
        code, _, body = self.get("/api/data?profile=alex&days=14", cookie=good)
        self.assertEqual((code, json.loads(body)["profile"]["id"]), (200, "alex"))
        self.assertEqual(json.loads(self.get("/manifest.webmanifest", cookie=good)[2])["start_url"], "/?key=" + key)
        # a device that holds the key may open the QR page to connect the next phone; without key: 401
        for path in ("/devices", "/devices.html", "/api/devices"):
            self.assertEqual(self.get(path, cookie=good)[0], 200, path)
            self.assertEqual(self.get(path)[0], 401, path)
        for bad_neighbour in ("a=b c; " + good, 'x="; ' + good, good + "; y=z"):
            self.assertEqual(self.get("/", cookie=bad_neighbour)[0], 200, bad_neighbour)
        self.assertEqual(self.get("/", cookie="bos_key=" + key[:-1] + "x")[0], 401)
        self.assertEqual(self.get("/", cookie='bos_key="unterminated')[0], 401)
        self.assertEqual(self.get("/", host="evil.example:%d" % self.port, cookie=good)[0], 403)  # DNS rebinding
        bos.ensure_server_key(self.key_path, rotate=True)
        self.assertEqual(self.get("/", cookie=good)[0], 401)  # rotation takes effect without restart

    def test_compare_api(self):
        code, h, body = self.get("/api/compare?days=14")
        self.assertEqual((code, h["content-type"]), (200, "application/json; charset=utf-8"))
        d = json.loads(body)
        self.assertEqual(([m["id"] for m in d["members"]], d["period"]["days"]), (["alex", "sam"], 14))
        self.assertNotIn("path", d["members"][0])
        self.assertEqual(json.loads(self.get("/api/compare")[2])["period"]["key"], "30")  # server default
        self.assertEqual(self.get("/api/compare?days=7")[0], 400)
        key = bos.ensure_server_key(self.key_path)
        self.srv.is_local = lambda ip: False  # a phone in the LAN: same key rule as everything else
        code, _, body = self.get("/api/compare?days=14")
        self.assertEqual(code, 401)
        self.assertNotIn(b"alex", body)
        self.assertEqual(self.get("/api/compare?days=14", cookie="bos_key=" + key)[0], 200)
        self.assertEqual(self.get("/api/compare?days=14", host="evil.example:%d" % self.port,
                                  cookie="bos_key=" + key)[0], 403)

    def test_host_check_allows_this_machines_names(self):
        p = self.port
        for host in ("localhost:%d" % p, "127.0.0.1:%d" % p, "[::1]:%d" % p, "%s:%d" % (bos.local_hostnames()[0], p)):
            self.assertEqual(self.get("/api/profiles", host=host)[0], 200, host)
        for ip in bos.lan_ipv4s():
            self.assertEqual(self.get("/api/profiles", host="%s:%d" % (ip, p))[0], 200, ip)
        for host in ("localhost:1", "localhost", "127.0.0.1:8040"):  # loopback names on any port (SSH tunnels)
            self.assertEqual(self.get("/api/profiles", host=host)[0], 200, host)
        for host in ("bodyos.home:%d" % p, "evil.example:%d" % p, "evil.example:1", "a:b:%d" % p):
            self.assertEqual(self.get("/api/profiles", host=host)[0], 403, host)
        cfg = bos.load_server_config(self.key_path)
        cfg["allowed_hosts"] = ["BodyOS.home"]
        bos.write_json_file(self.key_path, cfg, mode=0o600)
        self.assertEqual(self.get("/api/profiles", host="bodyos.home:%d" % p)[0], 200)

    def test_rotate_key_cli_and_single_user_key_location(self):
        code, out, _ = self.bos("dashboard", "--rotate-key")
        self.assertEqual(code, 0)
        k1 = bos.load_server_config(self.key_path)["key"]
        self.bos("dashboard", "--rotate-key")
        self.assertNotEqual(bos.load_server_config(self.key_path)["key"], k1)
        single = bos.Ctx(os.path.join(self.base, "people", "alex"), self.data, DEMO_TODAY)
        self.assertEqual(bos.server_json_path(single), os.path.join(self.data, "server.json"))
        self.assertTrue(bos.is_loopback_ip("127.0.0.1") and bos.is_loopback_ip("::1")
                        and bos.is_loopback_ip("::ffff:127.0.0.1"))
        self.assertFalse(bos.is_loopback_ip("192.168.1.20") or bos.is_loopback_ip("garbage"))
        links = bos.device_links("K" * 43, 8030)
        self.assertTrue(links and links[0]["link"].endswith(":8030/?key=" + "K" * 43))

    def test_single_user_profiles_endpoint(self):
        me = os.path.join(self.base, "people", "alex")
        srv = bos.make_dashboard_server(bos.Ctx(me, self.data, DEMO_TODAY), port=0, today=DEMO_TODAY)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.port, old = srv.server_address[1], self.port
            p = json.loads(self.get("/api/profiles")[2])
            self.assertEqual(([m["id"] for m in p["members"]], p["household"]), (["me"], None))
            self.assertEqual(json.loads(self.get("/api/data?profile=me")[2])["profile"]["id"], "me")
            self.assertEqual(self.get("/api/data?profile=alex")[0], 404)
            self.assertEqual(self.get("/api/compare?days=14")[0], 404)  # the comparison needs household mode
        finally:
            self.port = old
            srv.shutdown()
            srv.server_close()


class TestPwa(unittest.TestCase):
    DASH = os.path.join(ROOT, "tools", "dashboard")

    def test_icons_are_deterministic_and_committed(self):
        sys.path.insert(0, self.DASH)
        try:
            import make_icons
        finally:
            sys.path.remove(self.DASH)
        tmp = tempfile.mkdtemp(prefix="bos-icons-")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                make_icons.main(["make_icons.py", tmp])
            for name, size in make_icons.SIZES.items():
                with open(os.path.join(tmp, name), "rb") as f:
                    fresh = f.read()
                with open(os.path.join(self.DASH, "icons", name), "rb") as f:
                    self.assertEqual(f.read(), fresh, name)
                self.assertEqual(fresh[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct_unpack(fresh[16:24]), (size, size))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_manifest_meta_and_vendored_qr(self):
        with open(os.path.join(self.DASH, "manifest.webmanifest")) as f:
            man = json.load(f)
        self.assertEqual((man["name"], man["short_name"], man["display"]), ("body-os", "body-os", "standalone"))
        for icon in man["icons"]:
            self.assertTrue(os.path.exists(os.path.join(self.DASH, icon["src"])), icon["src"])
        with open(os.path.join(self.DASH, "index.html")) as f:
            html = f.read()
        for needle in ('rel="manifest" href="manifest.webmanifest" crossorigin="use-credentials"',
                       'rel="apple-touch-icon" href="icons/apple-touch-icon.png"', "viewport-fit=cover",
                       'name="apple-mobile-web-app-capable"', 'name="apple-mobile-web-app-status-bar-style"',
                       'name="theme-color" content="#f3f2ee" media="(prefers-color-scheme: light)"',
                       'name="theme-color" content="#111110" media="(prefers-color-scheme: dark)"'):
            self.assertIn(needle, html)
        with open(os.path.join(self.DASH, "app.js")) as f:
            self.assertNotIn("serviceWorker", f.read())
        vendor = os.path.join(self.DASH, "vendor")
        with open(os.path.join(vendor, "README.md")) as f:
            readme = f.read()
        with open(os.path.join(vendor, "qrcode.js"), "rb") as f:
            self.assertIn(hashlib.sha256(f.read()).hexdigest(), readme)
        self.assertTrue(os.path.exists(os.path.join(vendor, "QRCODE-LICENSE")))


def struct_unpack(b):
    import struct
    return struct.unpack(">II", b)


class TestService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bos-svc-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def svc(self, *argv, platform="darwin"):
        me = os.path.join(self.tmp, "me")
        data = os.path.join(self.tmp, "data")
        with mock.patch.dict(os.environ, {"HOME": self.home}), mock.patch.object(bos.sys, "platform", platform):
            return run("--me", me, "--data", data, "service", *argv)

    def test_install_dry_run_prints_plist_and_writes_nothing(self):
        import plistlib
        code, out, err = self.svc("install", "--port", "8099", "--lan", "--dry-run")
        self.assertEqual(code, 0, err)
        plist_path = os.path.join(self.home, "Library", "LaunchAgents", "io.body-os.dashboard.plist")
        self.assertIn("# would write " + plist_path, out)
        self.assertFalse(os.path.exists(plist_path))
        xml = out.split("\n", 1)[1].split("$ launchctl", 1)[0]
        pl = plistlib.loads(xml.encode())
        self.assertEqual(pl["Label"], "io.body-os.dashboard")
        self.assertTrue(pl["RunAtLoad"] and pl["KeepAlive"])
        self.assertEqual(pl["WorkingDirectory"], ROOT)
        args = pl["ProgramArguments"]
        self.assertEqual(args[0], sys.executable)
        self.assertTrue(os.path.isabs(args[0]) and args[1] == os.path.join(ROOT, "tools", "bos.py"))
        self.assertEqual(args[-4:], ["dashboard", "--port", "8099", "--lan"])
        self.assertIn("--me", args)
        log = os.path.join(self.tmp, "data", "dashboard.log")
        self.assertEqual((pl["StandardOutPath"], pl["StandardErrorPath"]), (log, log))
        self.assertIn("$ launchctl bootstrap gui/%d %s" % (os.getuid(), plist_path), out)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data")))
        code, out, _ = self.svc("uninstall", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("$ launchctl bootout gui/%d/io.body-os.dashboard" % os.getuid(), out)
        code, out, _ = self.svc("status", "--dry-run")
        self.assertIn("not installed", out)

    def test_linux_writes_a_systemd_user_unit(self):
        code, out, _ = self.svc("install", "--dry-run", "--lan", platform="linux")
        self.assertEqual(code, 0)
        self.assertIn("ExecStart=", out)
        self.assertIn("dashboard --port 8030 --lan", out)
        self.assertIn("$ systemctl --user enable --now body-os-dashboard.service", out)

    def test_other_platforms_are_a_clear_error(self):
        code, _, err = self.svc("install", "--dry-run", platform="win32")
        self.assertEqual(code, 2)
        self.assertIn("macOS", err)


if __name__ == "__main__":
    unittest.main()
