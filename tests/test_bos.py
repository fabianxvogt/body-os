"""Tests for tools/bos.py. Run: python3 -m unittest discover -s tests

All tests work on temporary copies; examples/demo-me is never written to.
"""

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
import unittest
import zipfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bos  # noqa: E402

DEMO = os.path.join(ROOT, "examples", "demo-me")
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
        }
        self.assertEqual({k: v["status"] for k, v in st.items()}, expected)
        self.assertEqual(st["oats-0001"]["remaining"], 880)
        self.assertEqual(st["rice-0001"]["remaining"], 600)
        self.assertEqual(st["tofu-0001"]["expires"], "2026-10-15")  # open event re-estimates expiry
        self.assertTrue(st["milk-0001"]["opened"])
        code, out, _ = self.bos("pantry")
        self.assertEqual(code, 0)
        self.assertNotIn("chicken", out)
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
    KEYS = ("schema", "today", "period", "language", "targets", "training_plan", "week", "days", "previous",
            "substance_kinds", "triggers_total", "trigger_order", "use_times", "sleep_vs_last_use", "lifts",
            "measures", "pantry", "cookbook")
    DAY_KEYS = ("day", "weight_kg", "weight_7d", "sleep_h", "sleep_quality", "wakeups", "kcal", "protein_g",
                "water_ml", "caffeine_n", "last_caffeine", "alcohol_units", "substance_n", "tobacco_n", "triggers",
                "last_substance", "training_n", "training_min", "energy", "mood", "stress")

    def test_demo_data_matches_summary(self):
        ctx = bos.Ctx(self.me, self.data, DEMO_TODAY)
        d = bos.dashboard_data(ctx, "14")
        for k in self.KEYS:
            self.assertIn(k, d)
        for k in self.DAY_KEYS:
            self.assertIn(k, d["days"][0])
        json.dumps(d)  # JSON-serialisable
        self.assertEqual((d["period"]["from"], d["period"]["to"], d["period"]["days"]), ("2026-09-30", "2026-10-13", 14))
        p = bos.build_summary(ctx, dt.date(2026, 9, 30), dt.date(2026, 10, 13))
        srows = {r["day"]: r for r in p["days"]}
        for r in d["days"]:
            s = srows[r["day"]]
            for k in ("weight_kg", "substance_n", "tobacco_n", "training_n", "training_min", "caffeine_n",
                      "last_substance", "kcal", "protein_g", "water_ml"):
                self.assertEqual(r[k], s[k], (r["day"], k))
            if s["sleep_h"] is not None:
                self.assertAlmostEqual(r["sleep_h"], s["sleep_h"], places=2)
            if s["weight_7d"] is not None:
                self.assertAlmostEqual(r["weight_7d"], s["weight_7d"], places=3)
            self.assertEqual(sum(r["triggers"].values()), r["substance_n"])
        per = p["period"]
        self.assertEqual(sum(r["substance_n"] for r in d["days"]), sum(per["substances_total"].values()))
        self.assertEqual(d["substance_kinds"], per["substances_total"])
        self.assertEqual(d["triggers_total"], per["substance_triggers"])
        self.assertEqual(sum(u["count"] for u in d["use_times"]), sum(per["substances_total"].values()))
        self.assertTrue(all(0 <= u["weekday"] <= 6 and 0 <= u["hour"] <= 23 for u in d["use_times"]))
        self.assertEqual(len(d["sleep_vs_last_use"]), sum(1 for r in p["days"] if r["sleep_h"] is not None))
        svu = {r["day"]: r for r in d["sleep_vs_last_use"]}
        self.assertEqual(svu["2026-10-02"]["last_use_prev_evening"], "22:40")  # 10-01 evening joint
        self.assertEqual(svu["2026-10-02"]["minutes_after_18"], 280)
        # lifts: <= 4 exercises, Epley e1RM, top set per day
        ex = d["lifts"]["exercises"]
        self.assertLessEqual(len(ex), 4)
        sq = {x["day"]: x for x in ex["squat"]}["2026-10-12"]
        self.assertEqual((sq["top_kg"], sq["top_reps"]), (72, 8))
        self.assertAlmostEqual(sq["e1rm"], round(72 * (1 + 8 / 30), 1))
        self.assertEqual([m["value"] for m in d["measures"]["waist_cm"]], [86.5, 85.5])
        self.assertEqual(len(d["measures"]["bp"]), 2)
        # pantry: non-gone, urgency order, same statuses as `bos pantry`
        self.assertEqual([x["item_id"] for x in d["pantry"]],
                         [x["item_id"] for x in bos.pantry_state(ctx) if x["status"] != "gone"])
        self.assertEqual(d["pantry"][0]["status"], "discard")
        self.assertEqual(len(d["cookbook"]), 4)
        self.assertEqual(d["cookbook"][0]["day"], max(c["day"] for c in d["cookbook"]))
        self.assertEqual(d["targets"], {"protein_g": 140})
        self.assertEqual(d["training_plan"], 4)
        self.assertEqual(d["week"]["from"], "2026-10-12")
        # 'all' starts at the first logged day; bad periods are rejected
        self.assertEqual(bos.dashboard_data(ctx, "all")["period"]["from"], "2026-09-30")
        self.assertEqual(len(bos.dashboard_data(ctx, 30)["days"]), 30)
        with self.assertRaises(bos.BosError):
            bos.dashboard_data(ctx, "7")

    def test_empty_instance_gives_valid_empty_structure(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        for period in ("14", "all"):
            d = bos.dashboard_data(bos.Ctx(empty, self.data, DEMO_TODAY), period)
            for k in self.KEYS:
                self.assertIn(k, d)
            self.assertEqual(d["period"]["days_logged"], 0)
            self.assertEqual(len(d["days"]), 14)
            self.assertTrue(all(r["weight_kg"] is None and r["substance_n"] == 0 for r in d["days"]))
            for k in ("use_times", "sleep_vs_last_use", "pantry", "cookbook", "trigger_order"):
                self.assertEqual(d[k], [])
            self.assertEqual(d["lifts"], {"exercises": {}, "others": []})
            self.assertEqual(d["language"], "en")
            json.dumps(d)

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


if __name__ == "__main__":
    unittest.main()
