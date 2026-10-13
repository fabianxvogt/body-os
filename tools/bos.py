#!/usr/bin/env python3
"""bos - body-os command line tool (Python 3.9+, standard library only).

Spec: docs/DATA_FORMAT.md and docs/ARCHITECTURE.md. Personal data lives in me/ (or --me DIR);
derived databases live in data/ (or --data DIR). Run `bos.py <command> -h` for details.
"""

import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import statistics
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------------------------
# Schema (docs/DATA_FORMAT.md)
# --------------------------------------------------------------------------------------------

LOG_TYPES = ("weight", "sleep", "meal", "drink", "substance", "training", "checkin", "symptom",
             "measure", "lab", "note")
PANTRY_TYPES = ("purchase", "consume", "discard", "adjust", "open")
SRC = ("chat", "photo", "device", "import", "estimate")
CONF = ("high", "med", "low")
MEAL_SLOTS = ("breakfast", "lunch", "dinner", "snack")
DRINK_KINDS = ("water", "coffee", "tea", "alcohol", "soft", "other")
SUBSTANCE_KINDS = ("joint", "cigarette", "vape", "cannabis_vape", "nicotine_replacement", "other")
TRAINING_KINDS = ("strength", "run", "bike", "walk", "sport", "other")
UNITS = ("g", "ml", "pcs")
STORAGE = ("fridge", "freezer", "pantry")
DATE_KINDS = ("best_before", "use_by", "none")
DISCARD_REASONS = ("expired", "spoiled", "other")
COOK_DEVICES = ("stove", "oven", "thermomix", "microwave", "none")
GRACE_DEFAULT = {"best_before": 7, "none": 2, "use_by": 0}
STATUS_ORDER = {"discard": 0, "check": 1, "soon": 2, "ok": 3, "gone": 4}

# Columns every type table gets in the SQLite build, so views and canned queries always work.
TYPE_FIELDS = {
    "weight": ["kg"],
    "sleep": ["bed", "wake", "quality", "wakeups", "dur_min", "deep_min", "rem_min"],
    "meal": ["slot", "desc", "items", "kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "pantry_used"],
    "drink": ["kind", "ml", "caffeine_mg", "alcohol_units"],
    "substance": ["kind", "count", "tobacco", "trigger", "g"],
    "training": ["kind", "plan", "dur_min", "sets", "distance_km", "avg_hr", "rpe"],
    "checkin": ["energy", "mood", "stress"],
    "symptom": ["desc", "severity"],
    "measure": ["metric", "value", "unit", "sys", "dia", "pulse"],
    "lab": ["test", "value", "unit", "ref_low", "ref_high", "lab_date"],
    "note": ["text", "tags"],
}
COMMON_FIELDS = ["id", "ts", "type", "src", "conf", "note"]

BLS_SHA256 = "12b7a6ba62807ec9b301eb276f897dc85f99b2292311618dec3749a12d984c91"
BLS_ATTRIBUTION = ("Max Rubner-Institut (2025), Bundeslebensmittelschlüssel (BLS), Version 4.0, "
                   "doi:10.25826/Data20251217-134202-0, licence CC BY 4.0")
BLS_HELP = ("BLS 4.0 archive (zip with the xlsx workbooks). Official download: https://blsdb.de "
            "(doi:10.25826/Data20251217-134202-0), licence CC BY 4.0. "
            "Default: data/sources/BLS_4_0_2025_DE.zip")
# BLS component codes for the summary columns in foods.
FOOD_COLUMNS = {"kcal": "ENERCC", "protein_g": "PROT625", "fat_g": "FAT", "carbs_g": "CHO",
                "fiber_g": "FIBT", "sugar_g": "SUGAR", "salt_g": "NACL"}
CALC_NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")


class BosError(Exception):
    pass


# --------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------

def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_ts(s):
    """Parse an ISO 8601 timestamp. Returns aware or naive datetime; raises ValueError."""
    if not isinstance(s, str):
        raise ValueError("not a string")
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s)


def parse_date(s):
    if not isinstance(s, str):
        raise ValueError("not a string")
    return dt.date.fromisoformat(s[:10]) if len(s) >= 10 and s[4] == "-" else dt.date.fromisoformat(s)


def local_day(ts):
    """Calendar day as written in the timestamp (its own local offset)."""
    return parse_ts(ts).date()


def hhmm(ts):
    return parse_ts(ts).strftime("%H:%M")


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


def ordered(ev):
    out = {k: ev[k] for k in ("id", "ts", "type") if k in ev}
    out.update((k, v) for k, v in ev.items() if k not in out)
    return out


def slug(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:32] or "item"


def norm_name(text):
    """Lowercase, strip diacritics and non-alphanumerics; used for space-insensitive search."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^0-9a-z]+", "", text.replace("ß", "ss"))


def read_jsonl(path):
    """Yield (line_no, obj_or_None, error_or_None) for each non-blank line."""
    with open(path, encoding="utf-8") as f:
        for no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                yield no, None, "invalid JSON: %s" % e.msg
                continue
            if not isinstance(obj, dict):
                yield no, None, "line is not a JSON object"
                continue
            yield no, obj, None


def load_events(path):
    if not os.path.exists(path):
        return []
    return [obj for _, obj, err in read_jsonl(path) if obj is not None]


class Ctx:
    """Resolved paths and settings for one invocation."""

    def __init__(self, me=None, data=None, today=None):
        self.root = ROOT
        self.me = os.path.abspath(me) if me else os.path.join(ROOT, "me")
        self.data = os.path.abspath(data) if data else os.path.join(ROOT, "data")
        self.settings = {}
        sp = os.path.join(self.me, "settings.json")
        if os.path.exists(sp):
            try:
                with open(sp, encoding="utf-8") as f:
                    self.settings = json.load(f) or {}
            except (OSError, json.JSONDecodeError):
                self.settings = {}
        self.tz = None
        tzname = self.settings.get("timezone") if isinstance(self.settings, dict) else None
        if tzname:
            try:
                from zoneinfo import ZoneInfo
                self.tz = ZoneInfo(tzname)
            except Exception:
                self.tz = None
        self.today = dt.date.fromisoformat(today) if today else self.now().date()

    def now(self):
        now = dt.datetime.now(self.tz) if self.tz else dt.datetime.now().astimezone()
        return now.replace(microsecond=0)

    def localize(self, naive):
        if self.tz:
            return naive.replace(tzinfo=self.tz)
        return naive.astimezone()

    def grace(self, date_kind, item=None):
        if item and is_int(item.get("grace_days")):
            return item["grace_days"]
        cfg = (self.settings.get("pantry") or {}).get("grace_days") or {}
        return cfg.get(date_kind, GRACE_DEFAULT.get(date_kind, 0))

    @property
    def log_dir(self):
        return os.path.join(self.me, "log")

    @property
    def pantry_path(self):
        return os.path.join(self.me, "pantry", "pantry.jsonl")

    @property
    def cookbook_path(self):
        return os.path.join(self.me, "recipes", "cookbook.jsonl")

    def log_files(self):
        out = []
        for base, _, files in os.walk(self.log_dir):
            out += [os.path.join(base, f) for f in files if f.endswith(".jsonl")]
        return sorted(out)

    def log_events(self):
        evs = []
        for p in self.log_files():
            evs += load_events(p)
        return evs


# --------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------

def _check_ts(ev, key, errs, required=True):
    if key not in ev:
        if required:
            errs.append("missing '%s'" % key)
        return None
    try:
        t = parse_ts(ev[key])
    except ValueError:
        errs.append("'%s' is not an ISO 8601 timestamp" % key)
        return None
    if t.tzinfo is None:
        errs.append("'%s' has no UTC offset (e.g. +02:00)" % key)
    return t


def _check_num(ev, key, errs, lo=None, hi=None, required=False, integer=False):
    if key not in ev or ev[key] is None:
        if required:
            errs.append("missing '%s'" % key)
        return
    v = ev[key]
    if not (is_int(v) if integer else is_num(v)):
        errs.append("'%s' must be %s" % (key, "an integer" if integer else "a number"))
    elif (lo is not None and v < lo) or (hi is not None and v > hi):
        errs.append("'%s'=%s out of range %s-%s" % (key, v, lo, hi))


def _check_enum(ev, key, allowed, errs, required=False):
    if key not in ev or ev[key] is None:
        if required:
            errs.append("missing '%s'" % key)
        return
    if ev[key] not in allowed:
        errs.append("'%s'=%r not one of %s" % (key, ev[key], "/".join(allowed)))


def _check_str(ev, key, errs, required=False):
    if key not in ev or ev[key] is None:
        if required:
            errs.append("missing '%s'" % key)
        return
    if not isinstance(ev[key], str) or (required and not ev[key].strip()):
        errs.append("'%s' must be a non-empty string" % key)


def _check_date(ev, key, errs, required=False):
    if key not in ev or ev[key] is None:
        if required:
            errs.append("missing '%s'" % key)
        return
    try:
        parse_date(ev[key])
    except (ValueError, TypeError, IndexError):
        errs.append("'%s' is not a date (YYYY-MM-DD)" % key)


def _check_common(ev, types, errs):
    _check_str(ev, "id", errs, required=True)
    _check_ts(ev, "ts", errs)
    _check_enum(ev, "type", types, errs, required=True)
    _check_enum(ev, "src", SRC, errs)
    _check_enum(ev, "conf", CONF, errs)
    _check_str(ev, "note", errs)


def validate_log_event(ev):
    errs = []
    if not isinstance(ev, dict):
        return ["event is not a JSON object"]
    _check_common(ev, LOG_TYPES, errs)
    t = ev.get("type")
    if t == "weight":
        _check_num(ev, "kg", errs, 20, 400, required=True)
    elif t == "sleep":
        bed = _check_ts(ev, "bed", errs, required="dur_min" not in ev)
        wake = _check_ts(ev, "wake", errs, required="dur_min" not in ev)
        if bed and wake and bed.tzinfo and wake.tzinfo and wake <= bed:
            errs.append("'wake' must be after 'bed'")
        if bed and wake and bed.tzinfo and wake.tzinfo and (wake - bed) > dt.timedelta(hours=24):
            errs.append("sleep longer than 24 h")
        _check_num(ev, "quality", errs, 1, 5, integer=True)
        _check_num(ev, "wakeups", errs, 0, 100, integer=True)
        for k in ("dur_min", "deep_min", "rem_min"):
            _check_num(ev, k, errs, 0, 1440)
    elif t == "meal":
        _check_enum(ev, "slot", MEAL_SLOTS, errs)
        if not ev.get("desc") and not ev.get("items"):
            errs.append("meal needs 'desc' or 'items'")
        _check_str(ev, "desc", errs)
        for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"):
            _check_num(ev, k, errs, 0, 20000)
        items = ev.get("items")
        if items is not None:
            if not isinstance(items, list):
                errs.append("'items' must be a list")
            else:
                for i, it in enumerate(items):
                    if not isinstance(it, dict) or not it.get("name"):
                        errs.append("items[%d] needs 'name'" % i)
                    elif "g" in it and (not is_num(it["g"]) or it["g"] < 0):
                        errs.append("items[%d].g must be a number >= 0" % i)
        used = ev.get("pantry_used")
        if used is not None:
            if not isinstance(used, list) or not all(isinstance(u, dict) and u.get("item_id") for u in used):
                errs.append("'pantry_used' must be a list of {item_id, qty}")
    elif t == "drink":
        _check_enum(ev, "kind", DRINK_KINDS, errs, required=True)
        _check_num(ev, "ml", errs, 0, 5000, required=True)
        _check_num(ev, "caffeine_mg", errs, 0, 1000)
        _check_num(ev, "alcohol_units", errs, 0, 50)
    elif t == "substance":
        _check_enum(ev, "kind", SUBSTANCE_KINDS, errs, required=True)
        _check_num(ev, "count", errs, 1, 100, integer=True)
        if "tobacco" in ev and not isinstance(ev["tobacco"], bool):
            errs.append("'tobacco' must be true/false")
        _check_str(ev, "trigger", errs)
        _check_num(ev, "g", errs, 0, 100)
    elif t == "training":
        _check_enum(ev, "kind", TRAINING_KINDS, errs, required=True)
        _check_num(ev, "dur_min", errs, 0, 1440)
        _check_num(ev, "distance_km", errs, 0, 1000)
        _check_num(ev, "avg_hr", errs, 30, 230)
        _check_num(ev, "rpe", errs, 1, 10)
        sets = ev.get("sets")
        if sets is not None:
            if not isinstance(sets, list):
                errs.append("'sets' must be a list")
            else:
                for i, s in enumerate(sets):
                    if not isinstance(s, dict) or not s.get("ex"):
                        errs.append("sets[%d] needs 'ex'" % i)
                        continue
                    if "kg" in s and s["kg"] is not None and (not is_num(s["kg"]) or s["kg"] < 0):
                        errs.append("sets[%d].kg must be a number >= 0" % i)
                    reps = s.get("reps")
                    if reps is not None and not (isinstance(reps, list) and all(is_int(r) and r >= 0 for r in reps)):
                        errs.append("sets[%d].reps must be a list of integers" % i)
    elif t == "checkin":
        if not any(k in ev for k in ("energy", "mood", "stress")):
            errs.append("checkin needs at least one of energy/mood/stress")
        for k in ("energy", "mood", "stress"):
            _check_num(ev, k, errs, 1, 5, integer=True)
    elif t == "symptom":
        _check_str(ev, "desc", errs, required=True)
        _check_num(ev, "severity", errs, 1, 5, integer=True, required=True)
    elif t == "measure":
        _check_str(ev, "metric", errs, required=True)
        if ev.get("metric") == "bp":
            _check_num(ev, "sys", errs, 50, 300, required=True)
            _check_num(ev, "dia", errs, 20, 200, required=True)
            _check_num(ev, "pulse", errs, 20, 250)
        else:
            _check_num(ev, "value", errs, required=True)
            _check_str(ev, "unit", errs)
    elif t == "lab":
        _check_str(ev, "test", errs, required=True)
        if "value" not in ev:
            errs.append("missing 'value'")
        _check_str(ev, "unit", errs)
        _check_num(ev, "ref_low", errs)
        _check_num(ev, "ref_high", errs)
        _check_date(ev, "lab_date", errs)
    elif t == "note":
        _check_str(ev, "text", errs, required=True)
        tags = ev.get("tags")
        if tags is not None and not (isinstance(tags, list) and all(isinstance(x, str) for x in tags)):
            errs.append("'tags' must be a list of strings")
    return errs


def validate_pantry_item(it, prefix="item"):
    errs = []
    if not isinstance(it, dict):
        return ["%s is not an object" % prefix]
    e = []
    _check_str(it, "item_id", e, required=True)
    _check_str(it, "name", e, required=True)
    _check_num(it, "qty", e, 0, 1e6, required=True)
    _check_enum(it, "unit", UNITS, e, required=True)
    _check_enum(it, "storage", STORAGE, e, required=True)
    _check_enum(it, "date_kind", DATE_KINDS, e, required=True)
    _check_date(it, "expires", e, required=True)
    _check_num(it, "price_eur", e, 0, 1e5)
    _check_num(it, "grace_days", e, 0, 365, integer=True)
    if "expires_est" in it and not isinstance(it["expires_est"], bool):
        e.append("'expires_est' must be true/false")
    errs += ["%s: %s" % (prefix, x) for x in e]
    return errs


def validate_pantry_event(ev, known_items=None):
    """known_items: {item_id: purchase ts} purchased so far (None = skip reference check)."""
    errs = []
    if not isinstance(ev, dict):
        return ["event is not a JSON object"]
    _check_common(ev, PANTRY_TYPES, errs)
    t = ev.get("type")
    if t == "purchase":
        items = ev.get("items")
        if not isinstance(items, list) or not items:
            errs.append("purchase needs a non-empty 'items' list")
        else:
            for i, it in enumerate(items):
                errs += validate_pantry_item(it, "items[%d]" % i)
    elif t in ("consume", "discard", "adjust", "open"):
        _check_str(ev, "item_id", errs, required=True)
        if known_items is not None and ev.get("item_id"):
            if ev["item_id"] not in known_items:
                errs.append("unknown item_id %r (no earlier purchase)" % ev["item_id"])
            elif _sort_key_ts(ev) < _sort_key_ts({"ts": known_items[ev["item_id"]]}):
                errs.append("ts is before the purchase of %r (%s)" % (ev["item_id"], known_items[ev["item_id"]]))
        if t == "consume":
            _check_num(ev, "qty", errs, 0, 1e6)
        elif t == "discard":
            _check_enum(ev, "reason", DISCARD_REASONS, errs, required=True)
        elif t == "adjust":
            _check_num(ev, "qty", errs, 0, 1e6)
            _check_enum(ev, "status", ("present", "gone"), errs)
        elif t == "open":
            _check_date(ev, "expires", errs)
    return errs


def validate_cookbook(ev):
    errs = []
    _check_str(ev, "id", errs, required=True)
    _check_ts(ev, "ts", errs)
    _check_str(ev, "name", errs, required=True)
    _check_enum(ev, "device", COOK_DEVICES, errs)
    _check_num(ev, "minutes", errs, 0, 2000)
    _check_num(ev, "servings", errs, 0, 100)
    _check_num(ev, "simplicity", errs, 1, 5, integer=True)
    _check_num(ev, "nutrition_score", errs, 1, 5, integer=True)
    _check_enum(ev, "status", ("suggested", "cooked"), errs)
    if ev.get("rating") not in (None, "up", "down"):
        errs.append("'rating' must be up/down/null")
    ps = ev.get("per_serving")
    if ps is not None and not isinstance(ps, dict):
        errs.append("'per_serving' must be an object")
    return errs


# --------------------------------------------------------------------------------------------
# Logging (log / pantry-log)
# --------------------------------------------------------------------------------------------

def read_input(args):
    if getattr(args, "file", None):
        with open(args.file, encoding="utf-8") as f:
            raw = f.read()
    elif args.json and args.json != "-":
        raw = args.json
    else:
        raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BosError("input is not valid JSON: %s" % e)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list) and all(isinstance(x, dict) for x in data):
        return data
    raise BosError("input must be a JSON object or an array of objects")


def _sum_known(vals):
    """Sum of numeric values; None when none is known (missing is not zero)."""
    nums = [v for v in vals if is_num(v)]
    return sum(nums) if nums else None


def _norm_ts_field(ctx, ev, key):
    """Attach the local offset to a naive timestamp so stored values always carry one."""
    if isinstance(ev.get(key), str):
        try:
            t = parse_ts(ev[key])
        except ValueError:
            return
        if t.tzinfo is None:
            ev[key] = ctx.localize(t).isoformat(timespec="seconds")
        else:
            ev[key] = (t.astimezone(ctx.tz) if ctx.tz else t.astimezone()).isoformat(timespec="seconds")


def new_id(prefix, ts, taken):
    stamp = parse_ts(ts).strftime("%Y%m%d%H%M%S")
    while True:
        cand = "%s-%s-%s" % (prefix, stamp, secrets.token_hex(2))
        if cand not in taken:
            taken.add(cand)
            return cand


def fill_defaults(ctx, ev, taken, ts_keys=("ts",)):
    ev = dict(ev)
    if not ev.get("ts"):
        ev["ts"] = ctx.now().isoformat(timespec="seconds")
    for k in ts_keys:
        _norm_ts_field(ctx, ev, k)
    ev.setdefault("src", "chat")
    if not ev.get("id") and isinstance(ev.get("type"), str):
        try:
            ev["id"] = new_id(ev["type"], ev["ts"], taken)
        except ValueError:
            pass  # invalid ts is reported by validation
    return ordered(ev)


def log_path_for(ctx, ts):
    t = parse_ts(ts)
    return os.path.join(ctx.log_dir, "%04d" % t.year, "%04d-%02d.jsonl" % (t.year, t.month))


def append_lines(path, events):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            f.write(dumps(ev) + "\n")


def cmd_log(ctx, args):
    taken = {e.get("id") for e in ctx.log_events()}
    events, problems = [], []
    for i, raw in enumerate(read_input(args)):
        ev = fill_defaults(ctx, raw, taken, ts_keys=("ts", "bed", "wake"))
        errs = validate_log_event(ev)
        if ev.get("id") in taken and raw.get("id"):
            errs.append("duplicate id %r" % ev["id"])
        taken.add(ev.get("id"))
        problems += ["event %d: %s" % (i, e) for e in errs]
        events.append(ev)
    if problems:
        raise BosError("nothing written:\n  " + "\n  ".join(problems))
    by_file = collections.OrderedDict()
    for ev in events:
        by_file.setdefault(log_path_for(ctx, ev["ts"]), []).append(ev)
    for path, evs in by_file.items():
        if not args.dry_run:
            append_lines(path, evs)
        for ev in evs:
            print(dumps(ev))
        print("%s %d event(s) -> %s" % ("would append" if args.dry_run else "appended", len(evs),
                                        os.path.relpath(path, ctx.me)), file=sys.stderr)
    return 0


def cmd_pantry_log(ctx, args):
    existing = load_events(ctx.pantry_path)
    taken = {e.get("id") for e in existing}
    known = {}
    for e in existing:
        if e.get("type") == "purchase":
            known.update((it.get("item_id"), e.get("ts")) for it in e.get("items") or [] if isinstance(it, dict))
    events, problems = [], []
    for i, raw in enumerate(read_input(args)):
        ev = fill_defaults(ctx, raw, taken)
        if ev.get("type") == "purchase" and isinstance(ev.get("items"), list):
            items = []
            for it in ev["items"]:
                if isinstance(it, dict) and not it.get("item_id") and it.get("name"):
                    it = dict(it, item_id="%s-%s" % (slug(it["name"]), secrets.token_hex(2)))
                    while it["item_id"] in known:
                        it["item_id"] = "%s-%s" % (slug(it["name"]), secrets.token_hex(2))
                items.append(it)
            ev["items"] = items
        errs = validate_pantry_event(ev, known)
        if ev.get("type") == "purchase":
            for it in ev.get("items") or []:
                if isinstance(it, dict) and it.get("item_id") in known:
                    errs.append("item_id %r already exists" % it["item_id"])
                if isinstance(it, dict):
                    known[it.get("item_id")] = ev.get("ts")
        problems += ["event %d: %s" % (i, e) for e in errs]
        events.append(ev)
    if problems:
        raise BosError("nothing written:\n  " + "\n  ".join(problems))
    if not args.dry_run:
        append_lines(ctx.pantry_path, events)
    for ev in events:
        print(dumps(ev))
    print("%s %d event(s) -> pantry/pantry.jsonl" % ("would append" if args.dry_run else "appended", len(events)),
          file=sys.stderr)
    return 0


# --------------------------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------------------------

def validate_all(ctx):
    """Return list of (relative path, line, message)."""
    problems = []
    rel = lambda p: os.path.relpath(p, ctx.me)
    ids = {}
    for path in ctx.log_files():
        m = re.search(r"(\d{4})-(\d{2})\.jsonl$", path)
        for no, ev, err in read_jsonl(path):
            if err:
                problems.append((rel(path), no, err))
                continue
            for e in validate_log_event(ev):
                problems.append((rel(path), no, e))
            try:
                t = parse_ts(ev.get("ts"))
                if m and (t.year, t.month) != (int(m.group(1)), int(m.group(2))):
                    problems.append((rel(path), no, "ts %s belongs in %04d-%02d.jsonl" % (ev["ts"], t.year, t.month)))
            except ValueError:
                pass
            if ev.get("id") in ids:
                problems.append((rel(path), no, "duplicate id %r (first at %s)" % (ev["id"], ids[ev["id"]])))
            else:
                ids[ev.get("id")] = "%s:%d" % (rel(path), no)
    if os.path.exists(ctx.pantry_path):
        known, pids, item_ids = {}, set(), set()
        for no, ev, err in read_jsonl(ctx.pantry_path):
            if err:
                problems.append((rel(ctx.pantry_path), no, err))
                continue
            for e in validate_pantry_event(ev, known):
                problems.append((rel(ctx.pantry_path), no, e))
            if ev.get("type") == "purchase":
                for it in ev.get("items") or []:
                    if isinstance(it, dict) and it.get("item_id"):
                        if it["item_id"] in item_ids:
                            problems.append((rel(ctx.pantry_path), no, "duplicate item_id %r" % it["item_id"]))
                        item_ids.add(it["item_id"])
                        known[it["item_id"]] = ev.get("ts")
            if ev.get("id") in pids:
                problems.append((rel(ctx.pantry_path), no, "duplicate id %r" % ev["id"]))
            pids.add(ev.get("id"))
    if os.path.exists(ctx.cookbook_path):
        cids = set()
        for no, ev, err in read_jsonl(ctx.cookbook_path):
            if err:
                problems.append((rel(ctx.cookbook_path), no, err))
                continue
            for e in validate_cookbook(ev):
                problems.append((rel(ctx.cookbook_path), no, e))
            if ev.get("id") in cids:
                problems.append((rel(ctx.cookbook_path), no, "duplicate id %r" % ev["id"]))
            cids.add(ev.get("id"))
    known_paths = set(ctx.log_files()) | {ctx.pantry_path, ctx.cookbook_path}
    for base, _, files in os.walk(ctx.me):
        if os.sep + ".git" in base + os.sep:
            continue
        for f in files:
            p = os.path.join(base, f)
            if f.endswith(".jsonl") and p not in known_paths:
                for no, ev, err in read_jsonl(p):
                    if err:
                        problems.append((rel(p), no, err))
    return problems


def cmd_validate(ctx, args):
    if not os.path.isdir(ctx.me):
        raise BosError("no instance folder at %s (run `bos.py init`)" % ctx.me)
    problems = validate_all(ctx)
    for path, no, msg in problems:
        print("%s:%d: %s" % (path, no, msg))
    files = len(ctx.log_files()) + os.path.exists(ctx.pantry_path) + os.path.exists(ctx.cookbook_path)
    print("%d problem(s) in %d file(s)" % (len(problems), files), file=sys.stderr)
    return 1 if problems else 0


# --------------------------------------------------------------------------------------------
# Pantry state
# --------------------------------------------------------------------------------------------

def _sort_key_ts(ev):
    try:
        return parse_ts(ev.get("ts")).timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0.0


def pantry_state(ctx, events=None):
    """Replay pantry events into a list of item dicts with derived status."""
    events = load_events(ctx.pantry_path) if events is None else events
    items = collections.OrderedDict()
    seq = sorted(enumerate(events), key=lambda p: (_sort_key_ts(p[1]), p[0]))
    for _, ev in seq:
        t = ev.get("type")
        if t == "purchase":
            for it in ev.get("items") or []:
                if not isinstance(it, dict) or not it.get("item_id"):
                    continue
                st = dict(it)
                st.update(remaining=it.get("qty"), purchased=(ev.get("ts") or "")[:10],
                          store=ev.get("store"), opened=False, gone=False, gone_reason=None)
                items[it["item_id"]] = st
            continue
        st = items.get(ev.get("item_id"))
        if st is None:
            continue
        if t == "consume":
            if is_num(ev.get("qty")) and is_num(st.get("remaining")):
                st["remaining"] = max(0, round(st["remaining"] - ev["qty"], 3))
                if st["remaining"] <= 0:
                    st["gone"], st["gone_reason"] = True, "consumed"
            else:
                st["remaining"], st["gone"], st["gone_reason"] = 0, True, "consumed"
        elif t == "discard":
            st["gone"], st["gone_reason"] = True, "discarded:%s" % ev.get("reason", "other")
        elif t == "adjust":
            if is_num(ev.get("qty")):
                st["remaining"] = ev["qty"]
                st["gone"] = ev["qty"] <= 0
                st["gone_reason"] = "adjusted" if st["gone"] else None
            if ev.get("status") == "gone":
                st["gone"], st["gone_reason"] = True, "adjusted"
            elif ev.get("status") == "present":
                st["gone"], st["gone_reason"] = False, None
            if "opened" in ev:
                st["opened"] = bool(ev["opened"])
        elif t == "open":
            st["opened"] = True
            st["opened_at"] = (ev.get("ts") or "")[:10]
            if ev.get("expires"):
                st["expires"] = ev["expires"]
                st["expires_est"] = True
    out = []
    for st in items.values():
        st["status"], st["days_left"] = item_status(ctx, st)
        out.append(st)
    out.sort(key=lambda s: (STATUS_ORDER[s["status"]],
                            s["days_left"] if s["days_left"] is not None else 99999, s.get("name", "")))
    return out


def item_status(ctx, st):
    """Return (status, days_left); days_left < 0 means past the date."""
    days_left = None
    try:
        days_left = (parse_date(st.get("expires")) - ctx.today).days
    except (ValueError, TypeError, IndexError):
        pass
    if st.get("gone"):
        return "gone", days_left
    if days_left is None:
        return "ok", None
    if days_left > 2:
        return "ok", days_left
    if days_left >= 0:
        return "soon", days_left
    kind = st.get("date_kind", "best_before")
    if kind == "use_by":
        return "discard", days_left
    if -days_left > ctx.grace(kind, st):
        return "discard", days_left
    return "check", days_left


def fmt_num(v, nd=0):
    if v is None:
        return "-"
    if nd == 0:
        return "%d" % round(v)
    s = ("%." + str(nd) + "f") % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def cmd_pantry(ctx, args):
    state = pantry_state(ctx)
    if not args.all:
        state = [s for s in state if s["status"] != "gone"]
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=1))
        return 0
    if not state:
        print("pantry empty")
        return 0
    print("pantry on %s (%d items)" % (ctx.today.isoformat(), len(state)))
    for s in state:
        dl = s["days_left"]
        when = "no date" if dl is None else ("%dd left" % dl if dl >= 0 else "%dd past" % -dl)
        qty = "%s%s" % (fmt_num(s.get("remaining"), 2), s.get("unit", ""))
        flags = []
        if s.get("opened"):
            flags.append("opened")
        if s.get("expires_est"):
            flags.append("est")
        line = "%-8s %-22s %-9s %-5s %s %s (%s)%s" % (
            s["status"], s.get("name", "?")[:22], qty, s.get("storage", ""), s.get("expires", "?"),
            when, s.get("date_kind", "?"), " [" + ",".join(flags) + "]" if flags else "")
        if s["status"] in ("check", "discard") and s.get("check_hint"):
            line += "  check: " + s["check_hint"]
        if s["status"] == "gone":
            line += "  " + (s.get("gone_reason") or "")
        print(line + "  id=" + s["item_id"])
    return 0


# --------------------------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------------------------

def sleep_minutes(ev):
    if is_num(ev.get("dur_min")):
        return ev["dur_min"]
    try:
        return (parse_ts(ev["wake"]) - parse_ts(ev["bed"])).total_seconds() / 60
    except (KeyError, ValueError, TypeError):
        return None


def event_day(ev):
    """Day an event is attributed to. Sleep counts for the morning you wake up."""
    try:
        if ev.get("type") == "sleep" and ev.get("wake"):
            return local_day(ev["wake"])
        return local_day(ev["ts"])
    except (ValueError, TypeError, KeyError):
        return None


def is_caffeinated(ev):
    return ev.get("kind") == "coffee" or (is_num(ev.get("caffeine_mg")) and ev["caffeine_mg"] > 0)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def daily_aggregates(events, days):
    """events: log events; days: list of dates. Returns {date: dict}."""
    wanted = set(days)
    agg = {d: collections.defaultdict(list) for d in days}
    for ev in events:
        d = event_day(ev)
        if d in wanted:
            agg[d][ev.get("type")].append(ev)
    out = {}
    for d in days:
        g = agg[d]
        r = {}
        w = sorted(g["weight"], key=lambda e: e["ts"])
        r["weight_kg"] = w[-1]["kg"] if w else None
        sl = g["sleep"]
        mins = [sleep_minutes(e) for e in sl]
        r["sleep_h"] = sum(m for m in mins if m is not None) / 60 if any(m is not None for m in mins) else None
        r["sleep_quality"] = _mean([e.get("quality") for e in sl])
        r["wakeups"] = sum(e.get("wakeups") or 0 for e in sl) if any("wakeups" in e for e in sl) else None
        meals = g["meal"]
        r["meals"] = len(meals)
        r["kcal"] = _sum_known([e.get("kcal") for e in meals])
        r["protein_g"] = _sum_known([e.get("protein_g") for e in meals])
        r["meals_missing_kcal"] = sum(1 for e in meals if not is_num(e.get("kcal")))
        drinks = g["drink"]
        r["water_ml"] = sum(e.get("ml") or 0 for e in drinks if e.get("kind") == "water")
        caf = sorted((e for e in drinks if is_caffeinated(e)), key=lambda e: e["ts"])
        r["caffeine_n"] = len(caf)
        r["caffeine_mg"] = sum(e.get("caffeine_mg") or 0 for e in caf)
        r["last_caffeine"] = hhmm(caf[-1]["ts"]) if caf else None
        r["alcohol_units"] = sum(e.get("alcohol_units") or 0 for e in drinks)
        subs = sorted(g["substance"], key=lambda e: e["ts"])
        r["substances"] = collections.Counter()
        for e in subs:
            r["substances"][e.get("kind", "other")] += e.get("count") or 1
        r["substance_n"] = sum(r["substances"].values())
        tob = [e for e in subs if e.get("tobacco")]
        r["tobacco_n"] = sum(e.get("count") or 1 for e in tob)
        r["last_substance"] = hhmm(subs[-1]["ts"]) if subs else None
        r["last_tobacco"] = hhmm(tob[-1]["ts"]) if tob else None
        tr = g["training"]
        r["training_n"] = len(tr)
        r["training_min"] = sum(e.get("dur_min") or 0 for e in tr)
        r["training_kinds"] = [e.get("kind") for e in tr]
        ck = g["checkin"]
        for k in ("energy", "mood", "stress"):
            r[k] = _mean([e.get(k) for e in ck])
        r["symptoms_n"] = len(g["symptom"])
        r["_events"] = g
        out[d] = r
    return out


def weight_trend(events, day):
    """Mean of weights logged in the 7 days ending on `day` (inclusive)."""
    lo = day - dt.timedelta(days=6)
    ws = [e["kg"] for e in events if e.get("type") == "weight" and is_num(e.get("kg"))
          and event_day(e) is not None and lo <= event_day(e) <= day]
    return statistics.mean(ws) if ws else None


def slope_per_week(points):
    """Least-squares slope (kg/week) of [(date, value)]."""
    if len(points) < 2:
        return None
    x0 = points[0][0]
    xs = [(d - x0).days for d, _ in points]
    ys = [v for _, v in points]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den * 7


def resolve_period(ctx, args):
    to = dt.date.fromisoformat(args.to) if args.to else ctx.today
    if args.frm:
        frm = dt.date.fromisoformat(args.frm)
    else:
        frm = to - dt.timedelta(days=(args.days or 7) - 1)
    if frm > to:
        raise BosError("--from is after --to")
    return frm, to


def build_summary(ctx, frm, to, notes=False):
    events = ctx.log_events()
    days = [frm + dt.timedelta(days=i) for i in range((to - frm).days + 1)]
    daily = daily_aggregates(events, days)
    for d in days:
        daily[d]["weight_7d"] = weight_trend(events, d)
    rows = [daily[d] for d in days]
    logged = [r for r in rows if any(r["_events"].values())]

    def avg(key, only=None):
        src = only if only is not None else rows
        return _mean([r[key] for r in src])

    meal_days = [r for r in rows if r["meals"]]
    wpts = [(d, daily[d]["weight_kg"]) for d in days if daily[d]["weight_kg"] is not None]
    subs_total = collections.Counter()
    triggers = collections.Counter()
    train_kinds = collections.Counter()
    for r in rows:
        subs_total.update(r["substances"])
        train_kinds.update(r["training_kinds"])
        for e in r["_events"]["substance"]:
            triggers[e.get("trigger") or "?"] += e.get("count") or 1
    sev = [e.get("severity") for r in rows for e in r["_events"]["symptom"]]
    measures, labs = {}, {}
    for r in rows:
        for e in r["_events"]["measure"]:
            v = "%s/%s" % (e.get("sys"), e.get("dia")) if e.get("metric") == "bp" else e.get("value")
            measures[e.get("metric")] = {"value": v, "unit": e.get("unit") or ("mmHg" if e.get("metric") == "bp" else ""),
                                         "day": e["ts"][:10]}
        for e in r["_events"]["lab"]:
            labs[e.get("test")] = {"value": e.get("value"), "unit": e.get("unit"), "ref_low": e.get("ref_low"),
                                   "ref_high": e.get("ref_high"), "lab_date": e.get("lab_date") or e["ts"][:10]}
    n = len(days)
    period = {
        "from": frm.isoformat(), "to": to.isoformat(), "days": n, "days_logged": len(logged),
        "weight_first": wpts[0][1] if wpts else None, "weight_last": wpts[-1][1] if wpts else None,
        "weight_7d_end": daily[days[-1]]["weight_7d"], "weight_slope_kg_per_week": slope_per_week(wpts),
        "sleep_h": avg("sleep_h"), "sleep_quality": avg("sleep_quality"), "wakeups": avg("wakeups"),
        "kcal_per_day": avg("kcal", meal_days), "protein_g_per_day": avg("protein_g", meal_days),
        "meal_days": len(meal_days), "meals_missing_kcal": sum(r["meals_missing_kcal"] for r in rows),
        "water_ml_per_day": avg("water_ml", logged) if logged else None,
        "caffeine_per_day": sum(r["caffeine_n"] for r in rows) / n,
        "alcohol_units_total": sum(r["alcohol_units"] for r in rows),
        "substances_total": dict(subs_total), "substances_per_day": sum(subs_total.values()) / n,
        "tobacco_total": sum(r["tobacco_n"] for r in rows), "substance_triggers": dict(triggers.most_common()),
        "training_sessions": sum(r["training_n"] for r in rows), "training_min": sum(r["training_min"] for r in rows),
        "training_kinds": dict(train_kinds),
        "energy": avg("energy"), "mood": avg("mood"), "stress": avg("stress"),
        "symptoms": len(sev), "symptom_severity": _mean(sev),
        "measures_latest": measures, "labs_latest": labs,
    }
    day_rows = []
    for d in days:
        r = dict(daily[d])
        r.pop("_events")
        r["substances"] = dict(r["substances"])
        r["day"] = d.isoformat()
        r.pop("training_kinds")
        day_rows.append(r)
    out = {"period": period, "days": day_rows}
    if notes:
        nl = []
        for d in days:
            g = daily[d]["_events"]
            for t in LOG_TYPES:
                for e in g[t]:
                    txt = e.get("text") if t == "note" else e.get("desc") if t == "symptom" else None
                    if txt:
                        nl.append({"day": d.isoformat(), "type": t, "text": txt})
                    if e.get("note"):
                        nl.append({"day": d.isoformat(), "type": t, "text": e["note"]})
        out["notes"] = nl
    return out


def cmd_summary(ctx, args):
    frm, to = resolve_period(ctx, args)
    s = build_summary(ctx, frm, to, notes=args.notes)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    p = s["period"]
    f1, f2 = (lambda v: fmt_num(v, 1)), (lambda v: fmt_num(v, 2))
    print("body-os summary %s..%s (%d days, %d with entries)" % (p["from"], p["to"], p["days"], p["days_logged"]))
    fmt = "%-5s %-5s %-5s %-5s %-2s %-2s %-5s %-4s %-5s %-3s %-5s %-3s %-3s %-3s %-5s %-6s %-3s %-3s %-3s %s"
    print(fmt % ("day", "wt", "wt7d", "sleep", "q", "wk", "kcal", "prot", "water", "caf", "last", "alc", "sub", "tob",
                 "last", "trn", "E", "M", "S", "sym"))
    for r in s["days"]:
        print(fmt % (
            r["day"][5:], f1(r["weight_kg"]), f1(r["weight_7d"]), f1(r["sleep_h"]), f1(r["sleep_quality"]),
            fmt_num(r["wakeups"]), fmt_num(r["kcal"]), fmt_num(r["protein_g"]),
            fmt_num(r["water_ml"]) if r["water_ml"] else "-", r["caffeine_n"] or "-", r["last_caffeine"] or "-",
            f1(r["alcohol_units"]) if r["alcohol_units"] else "-", r["substance_n"] or "-", r["tobacco_n"] or "-",
            r["last_substance"] or "-", ("%d/%dm" % (r["training_n"], r["training_min"])) if r["training_n"] else "-",
            f1(r["energy"]), f1(r["mood"]), f1(r["stress"]), r["symptoms_n"] or "-"))
    print("columns: wt kg (last of day), wt7d 7-day mean, sleep h + quality 1-5 + wakeups (night ending that day),"
          " kcal/prot g, water ml, caf = caffeinated drinks + last time, alc units, sub = substance count,"
          " tob = tobacco count, last = last substance time, trn = sessions/min, E/M/S = energy/mood/stress 1-5,"
          " sym = symptoms")
    print("period:")
    if p["weight_last"] is not None:
        print("  weight %s -> %s kg, 7d mean %s, trend %s kg/week" % (
            f1(p["weight_first"]), f1(p["weight_last"]), f2(p["weight_7d_end"]), f2(p["weight_slope_kg_per_week"])))
    print("  sleep %s h/night, quality %s, wakeups %s" % (f1(p["sleep_h"]), f1(p["sleep_quality"]), f1(p["wakeups"])))
    print("  food %s kcal, %s g protein per logged day (%d days; %d meals without kcal)" % (
        fmt_num(p["kcal_per_day"]), fmt_num(p["protein_g_per_day"]), p["meal_days"], p["meals_missing_kcal"]))
    print("  water %s ml/day, caffeine %s drinks/day, alcohol %s units total" % (
        fmt_num(p["water_ml_per_day"]), f1(p["caffeine_per_day"]), f1(p["alcohol_units_total"])))
    if p["substances_total"]:
        print("  substances %s/day: %s; tobacco %d; triggers: %s" % (
            f1(p["substances_per_day"]), ", ".join("%s %d" % kv for kv in sorted(p["substances_total"].items())),
            p["tobacco_total"], ", ".join("%s %d" % kv for kv in p["substance_triggers"].items())))
    print("  training %d sessions, %d min (%s)" % (p["training_sessions"], p["training_min"],
                                                    ", ".join("%s %d" % kv for kv in sorted(p["training_kinds"].items())) or "-"))
    print("  check-in energy %s, mood %s, stress %s; symptoms %d (mean severity %s)" % (
        f1(p["energy"]), f1(p["mood"]), f1(p["stress"]), p["symptoms"], f1(p["symptom_severity"])))
    if p["measures_latest"]:
        print("  measures (latest): " + ", ".join("%s %s%s (%s)" % (k, v["value"], v["unit"], v["day"][5:])
                                                  for k, v in sorted(p["measures_latest"].items())))
    if p["labs_latest"]:
        print("  labs (latest): " + ", ".join("%s %s %s [%s-%s] (%s)" % (
            k, v["value"], v["unit"] or "", fmt_num(v["ref_low"], 2), fmt_num(v["ref_high"], 2), v["lab_date"])
            for k, v in sorted(p["labs_latest"].items())))
    if args.notes:
        print("notes:")
        for n_ in s.get("notes", []):
            print("  %s %s: %s" % (n_["day"][5:], n_["type"], n_["text"]))
    return 0


# --------------------------------------------------------------------------------------------
# build (SQLite for Datasette)
# --------------------------------------------------------------------------------------------

def flatten(ev):
    """Flatten one level of nested dicts (key_sub); lists/other dicts become JSON text."""
    out = {}
    for k, v in ev.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out["%s_%s" % (k, k2)] = dumps(v2) if isinstance(v2, (list, dict)) else v2
        elif isinstance(v, list):
            out[k] = dumps(v)
        elif isinstance(v, bool):
            out[k] = int(v)
        else:
            out[k] = v
    return out


def _sqltype(values):
    vals = [v for v in values if v is not None]
    if vals and all(is_int(v) for v in vals):
        return "INTEGER"
    if vals and all(is_num(v) for v in vals):
        return "REAL"
    return "TEXT"


def q(name):
    return '"%s"' % name.replace('"', '""')


def _fold_case(row, cols):
    """Map keys differing only in case onto the canonical column (first value wins)."""
    canon = {c.lower(): c for c in cols}
    out = {}
    for k, v in row.items():
        c = canon[k.lower()]
        if c not in out:
            out[c] = v
    return out


def write_table(con, name, rows, base_cols=()):
    cols, seen = [], set()
    for k in list(base_cols) + [k for r in rows for k in r]:
        if k.lower() not in seen:  # SQLite column names are case-insensitive
            seen.add(k.lower())
            cols.append(k)
    rows = [_fold_case(r, cols) for r in rows]
    types = {c: _sqltype([r.get(c) for r in rows]) for c in cols}
    con.execute("CREATE TABLE %s (%s)" % (q(name), ", ".join("%s %s" % (q(c), types[c]) for c in cols)))
    con.executemany("INSERT INTO %s VALUES (%s)" % (q(name), ",".join("?" * len(cols))),
                    [[r.get(c) for c in cols] for r in rows])


DAILY_VIEW = """
CREATE VIEW daily AS
WITH days AS (
  SELECT day FROM weight UNION SELECT day FROM sleep UNION SELECT day FROM meal
  UNION SELECT day FROM drink UNION SELECT day FROM substance UNION SELECT day FROM training
  UNION SELECT day FROM checkin UNION SELECT day FROM symptom
)
SELECT d.day,
  (SELECT kg FROM weight w WHERE w.day = d.day ORDER BY ts DESC LIMIT 1) AS weight_kg,
  (SELECT ROUND(SUM(sleep_min) / 60.0, 2) FROM sleep s WHERE s.day = d.day) AS sleep_h,
  (SELECT AVG(quality) FROM sleep s WHERE s.day = d.day) AS sleep_quality,
  (SELECT SUM(wakeups) FROM sleep s WHERE s.day = d.day) AS wakeups,
  (SELECT SUM(kcal) FROM meal m WHERE m.day = d.day) AS kcal,
  (SELECT SUM(protein_g) FROM meal m WHERE m.day = d.day) AS protein_g,
  (SELECT SUM(ml) FROM drink k WHERE k.day = d.day AND k.kind = 'water') AS water_ml,
  (SELECT COUNT(*) FROM drink k WHERE k.day = d.day AND (k.kind = 'coffee' OR k.caffeine_mg > 0)) AS caffeine_n,
  (SELECT MAX(clock) FROM drink k WHERE k.day = d.day AND (k.kind = 'coffee' OR k.caffeine_mg > 0)) AS last_caffeine,
  (SELECT SUM(alcohol_units) FROM drink k WHERE k.day = d.day) AS alcohol_units,
  (SELECT SUM(COALESCE("count", 1)) FROM substance x WHERE x.day = d.day) AS substance_n,
  (SELECT SUM(COALESCE("count", 1)) FROM substance x WHERE x.day = d.day AND x.tobacco = 1) AS tobacco_n,
  (SELECT MAX(clock) FROM substance x WHERE x.day = d.day) AS last_substance,
  (SELECT COUNT(*) FROM training t WHERE t.day = d.day) AS training_n,
  (SELECT SUM(dur_min) FROM training t WHERE t.day = d.day) AS training_min,
  (SELECT AVG(energy) FROM checkin c WHERE c.day = d.day) AS energy,
  (SELECT AVG(mood) FROM checkin c WHERE c.day = d.day) AS mood,
  (SELECT AVG(stress) FROM checkin c WHERE c.day = d.day) AS stress,
  (SELECT COUNT(*) FROM symptom y WHERE y.day = d.day) AS symptoms_n
FROM days d WHERE d.day IS NOT NULL ORDER BY d.day
"""

CANNED_QUERIES = {
    "weight_trend": {
        "title": "Weight with 7-day rolling mean",
        "sql": "SELECT day, weight_kg, ROUND(AVG(weight_kg) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)"
               " AS weight_7d FROM daily WHERE weight_kg IS NOT NULL ORDER BY day",
    },
    "sleep_vs_last_joint": {
        "title": "Sleep vs. time of the last joint the evening before",
        "sql": "SELECT s.day, ROUND(s.sleep_min / 60.0, 2) AS sleep_h, s.quality, s.wakeups,"
               " (SELECT MAX(x.clock) FROM substance x WHERE x.kind = 'joint' AND x.day = date(s.day, '-1 day'))"
               " AS last_joint_prev_day FROM sleep s ORDER BY s.day",
    },
    "protein_per_day": {
        "title": "Protein and energy per day",
        "sql": "SELECT day, protein_g, kcal FROM daily WHERE kcal IS NOT NULL OR protein_g IS NOT NULL ORDER BY day",
    },
    "substance_per_day_by_trigger": {
        "title": "Substance use per day by trigger",
        "sql": "SELECT day, kind, COALESCE(\"trigger\", '?') AS \"trigger\", SUM(COALESCE(\"count\", 1)) AS n"
               " FROM substance GROUP BY day, kind, \"trigger\" ORDER BY day, n DESC",
    },
    "pantry_expiring": {
        "title": "Pantry items to use, check or discard",
        "sql": "SELECT status, name, remaining, unit, storage, expires, days_left, date_kind, check_hint, item_id"
               " FROM pantry_items WHERE status IN ('soon', 'check', 'discard')"
               " ORDER BY CASE status WHEN 'discard' THEN 0 WHEN 'check' THEN 1 ELSE 2 END, days_left",
    },
}


def build_db(ctx, path):
    events = ctx.log_events()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    by_type = {t: [] for t in LOG_TYPES}
    sets = []
    for ev in events:
        t = ev.get("type")
        if t not in by_type:
            continue
        row = flatten(ev)
        for k in ("day", "clock"):
            if k in row:
                row["x_" + k] = row.pop(k)
        d = event_day(ev)
        row["day"] = d.isoformat() if d else None
        try:
            row["clock"] = hhmm(ev["ts"])
        except (ValueError, KeyError, TypeError):
            row["clock"] = None
        if t == "sleep":
            row["sleep_min"] = sleep_minutes(ev)
        if t == "training":
            set_no = 0
            for s in ev.get("sets") or []:
                if not isinstance(s, dict):
                    continue
                for reps in s.get("reps") or [None]:
                    set_no += 1
                    kg = s.get("kg")
                    sets.append({"event_id": ev.get("id"), "day": row["day"], "plan": ev.get("plan"), "ex": s.get("ex"),
                                 "set_no": set_no, "kg": kg, "reps": reps,
                                 "volume_kg": kg * reps if is_num(kg) and is_int(reps) else None})
        by_type[t].append(row)
    base_extra = ["day", "clock"]
    for t, rows in by_type.items():
        cols = COMMON_FIELDS + TYPE_FIELDS[t] + base_extra + (["sleep_min"] if t == "sleep" else [])
        write_table(con, t, rows, cols)
    write_table(con, "sets", sets, ["event_id", "day", "plan", "ex", "set_no", "kg", "reps", "volume_kg"])
    pevents = load_events(ctx.pantry_path)
    write_table(con, "pantry_events", [flatten(e) for e in pevents], ["id", "ts", "type", "item_id", "qty", "reason"])
    items = []
    for s in pantry_state(ctx, pevents):
        r = flatten(s)
        items.append(r)
    write_table(con, "pantry_items", items,
                ["item_id", "name", "status", "days_left", "remaining", "qty", "unit", "category", "storage",
                 "date_kind", "expires", "expires_est", "check_hint", "opened", "purchased", "store", "price_eur",
                 "food_id", "gone_reason"])
    write_table(con, "cookbook", [flatten(e) for e in load_events(ctx.cookbook_path)],
                ["id", "ts", "name", "cuisine", "device", "minutes", "servings", "simplicity", "nutrition_score",
                 "per_serving_kcal", "per_serving_protein_g", "status", "rating", "skill", "source", "notes"])
    con.execute(DAILY_VIEW)
    for t in LOG_TYPES:
        con.execute("CREATE INDEX %s ON %s(day)" % (q("idx_%s_day" % t), q(t)))
    con.execute("CREATE TABLE _build (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO _build VALUES (?, ?)", [
        ("built_at", ctx.now().isoformat()), ("today", ctx.today.isoformat()),
        ("note", "Disposable build product of me/*.jsonl; rebuild with `bos.py build`.")])
    con.commit()
    counts = {t: len(by_type[t]) for t in LOG_TYPES}
    counts.update(sets=len(sets), pantry_items=len(items), pantry_events=len(pevents))
    con.close()
    os.replace(tmp, path)
    meta = {
        "title": "body-os",
        "description": "Personal health log (local only). Rebuilt from me/*.jsonl by `bos.py build`.",
        "databases": {"body-os": {"queries": CANNED_QUERIES}},
    }
    with open(os.path.join(os.path.dirname(path), "datasette-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return counts


def cmd_build(ctx, args):
    path = os.path.join(ctx.data, "body-os.sqlite")
    counts = build_db(ctx, path)
    print("built %s" % path)
    print("  " + ", ".join("%s %d" % kv for kv in counts.items()))
    print("  metadata %s" % os.path.join(ctx.data, "datasette-metadata.json"))
    return 0


def cmd_dash(ctx, args):
    cmd_build(ctx, args)
    uvx = shutil.which("uvx")
    if not uvx:
        print("uvx not found. Install uv (https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`"
              " or `brew install uv`, then rerun. Alternatively: `pipx run datasette ...`.", file=sys.stderr)
        return 1
    db = os.path.join(ctx.data, "body-os.sqlite")
    meta = os.path.join(ctx.data, "datasette-metadata.json")
    print("dashboard: http://127.0.0.1:%d/  (localhost only, Ctrl+C to stop)" % args.port, flush=True)
    os.execvp(uvx, [uvx, "datasette", db, "-m", meta, "--host", "127.0.0.1", "--port", str(args.port)])


# --------------------------------------------------------------------------------------------
# init / doctor
# --------------------------------------------------------------------------------------------

def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def is_own_repo(path):
    if not os.path.isdir(path):
        return False
    r = git(["rev-parse", "--show-toplevel"], path)
    return r.returncode == 0 and os.path.realpath(r.stdout.strip()) == os.path.realpath(path)


def cmd_init(ctx, args):
    tpl = os.path.join(ctx.root, "templates", "me")
    os.makedirs(ctx.me, exist_ok=True)
    copied = 0
    if os.path.isdir(tpl):
        for base, _, files in os.walk(tpl):
            dst_dir = os.path.join(ctx.me, os.path.relpath(base, tpl))
            os.makedirs(dst_dir, exist_ok=True)
            for f in files:
                dst = os.path.join(dst_dir, f)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(base, f), dst)
                    copied += 1
    for sub in ("log", "pantry", "recipes", "plans", "reviews", "doctor", "inbox"):
        os.makedirs(os.path.join(ctx.me, sub), exist_ok=True)
    print("copied %d template file(s) into %s" % (copied, ctx.me))
    if not is_own_repo(ctx.me):
        r = git(["init", "-q"], ctx.me)
        print("git init in me/: %s" % ("ok" if r.returncode == 0 else r.stderr.strip()))
    else:
        print("me/ is already a git repository")
    r = git(["config", "core.hooksPath", ".githooks"], ctx.root)
    print("engine hooks: %s" % ("core.hooksPath=.githooks" if r.returncode == 0 else r.stderr.strip()))
    return 0


def cmd_doctor(ctx, args):
    fails = warns = 0

    def report(level, msg):
        nonlocal fails, warns
        fails += level == "FAIL"
        warns += level == "WARN"
        print("%-4s %s" % (level, msg))

    if not os.path.isdir(ctx.me):
        report("FAIL", "no instance folder at %s - run `bos.py init`" % ctx.me)
    else:
        report("OK", "instance folder %s" % ctx.me)
        if is_own_repo(ctx.me):
            report("OK", "me/ is its own git repository")
            remotes = git(["remote", "-v"], ctx.me).stdout.strip()
            if remotes:
                report("WARN", "!!! me/ HAS A GIT REMOTE - personal health data could be pushed. "
                               "Remove it unless this is deliberate:\n     " + remotes.replace("\n", "\n     "))
            else:
                report("OK", "me/ has no remote")
        else:
            report("FAIL", "me/ is not its own git repository - run `bos.py init`")
        inside = os.path.realpath(ctx.me).startswith(os.path.realpath(ctx.root) + os.sep)
        if inside:
            r = git(["check-ignore", "-q", os.path.relpath(ctx.me, ctx.root) + "/"], ctx.root)
            if r.returncode == 0:
                report("OK", "instance folder is git-ignored by the engine repo")
            else:
                report("FAIL", "instance folder is NOT ignored by the engine repo - check .gitignore")
        else:
            report("OK", "instance folder is outside the engine repo")
        problems = validate_all(ctx)
        if problems:
            report("FAIL", "%d data problem(s); run `bos.py validate`" % len(problems))
        else:
            report("OK", "jsonl files valid")
    hp = git(["config", "--get", "core.hooksPath"], ctx.root).stdout.strip()
    if hp == ".githooks":
        report("OK", "engine hooks enabled (core.hooksPath=.githooks)")
    else:
        report("FAIL", "engine hooks not enabled - run `git config core.hooksPath .githooks` (or `bos.py init`)")
    for h in ("pre-commit", "pre-push"):
        p = os.path.join(ctx.root, ".githooks", h)
        if not (os.path.isfile(p) and os.access(p, os.X_OK)):
            report("FAIL", ".githooks/%s missing or not executable" % h)
    r = git(["check-ignore", "-q", "data/"], ctx.root)
    report("OK" if r.returncode == 0 else "FAIL", "data/ is %sgit-ignored" % ("" if r.returncode == 0 else "NOT "))
    print("%d failure(s), %d warning(s)" % (fails, warns))
    return 1 if fails else 0


# --------------------------------------------------------------------------------------------
# foods-import (BLS 4.0)
#
# Workbook layout and value markers follow Supper-Board's importer (scripts/import-bls/parse.ts,
# MIT licence, same author); this is an independent stdlib re-implementation.
# --------------------------------------------------------------------------------------------

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_MEMBER = 256 * 1024 * 1024
MARKERS = {"": "missing", "-": "missing", "TR": "trace", "<LOD": "below_lod", "<LOQ": "below_loq",
           "<LOD OR <LOQ": "below_lod_or_loq"}


def _col_index(ref):
    m = re.match(r"([A-Z]+)(\d+)$", ref or "")
    if not m:
        raise BosError("bad cell reference %r" % ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n


def _safe_open(zf, name):
    info = zf.getinfo(name)
    if info.file_size > MAX_MEMBER:
        raise BosError("archive member too large: %s" % name)
    head = zf.open(name).read(4096)
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise BosError("DTD/entity declarations not allowed: %s" % name)
    return zf.open(name)


def _sheet_path(zf):
    wb = ET.parse(_safe_open(zf, "xl/workbook.xml")).getroot()
    sheets = wb.findall("%ssheets/%ssheet" % (NS, NS))
    if len(sheets) != 1:
        raise BosError("expected one worksheet, found %d" % len(sheets))
    rid = sheets[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    rels = ET.parse(_safe_open(zf, "xl/_rels/workbook.xml.rels")).getroot()
    for rel in rels:
        if rel.get("Id") == rid:
            target = rel.get("Target", "")
            if rel.get("TargetMode") == "External" or ".." in target or target.startswith("/"):
                raise BosError("unsafe worksheet target %r" % target)
            return target if target.startswith("xl/") else "xl/" + target
    raise BosError("worksheet relationship missing")


def xlsx_rows(data):
    """Yield (row_number, {col_index: ("s"|"n", value)}) from the single sheet of an xlsx (bytes)."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    strings = []
    if "xl/sharedStrings.xml" in zf.namelist():
        for _, el in ET.iterparse(_safe_open(zf, "xl/sharedStrings.xml")):
            if el.tag == NS + "si":
                strings.append("".join(t.text or "" for t in el.iter(NS + "t")))
                el.clear()
    for _, el in ET.iterparse(_safe_open(zf, _sheet_path(zf))):
        if el.tag != NS + "row":
            continue
        cells = {}
        for c in el.findall(NS + "c"):
            t = c.get("t")
            v = c.find(NS + "v")
            if t == "s":
                cells[_col_index(c.get("r"))] = ("s", strings[int(v.text)])
            elif t == "inlineStr":
                cells[_col_index(c.get("r"))] = ("s", "".join(x.text or "" for x in c.iter(NS + "t")))
            elif t in ("str", "e"):
                cells[_col_index(c.get("r"))] = ("s", v.text if v is not None else "")
            elif v is not None and v.text is not None:
                cells[_col_index(c.get("r"))] = ("n", v.text)
        yield int(el.get("r")), cells
        el.clear()


def _text(cells, col):
    c = cells.get(col)
    return "" if c is None else c[1]


def parse_bls(zip_path):
    """Open the archive; return (outer zip, data workbook member name, components by code)."""
    outer = zipfile.ZipFile(zip_path)
    names = [n for n in outer.namelist() if not n.endswith("/")]
    for n in names:
        if n.startswith("/") or ".." in n.split("/"):
            raise BosError("unsafe archive path %r" % n)
    data_x = [n for n in names if re.search(r"_Daten_\d{4}_DE\.xlsx$", n)]
    comp_x = [n for n in names if n.endswith("_Components_DE_EN.xlsx")]
    if len(data_x) != 1:
        raise BosError("archive does not contain exactly one BLS *_Daten_*_DE.xlsx workbook")
    for n in data_x + comp_x:
        if outer.getinfo(n).file_size > MAX_MEMBER:
            raise BosError("archive member too large: %s" % n)
    components = {}
    if comp_x:
        rows = xlsx_rows(outer.read(comp_x[0]))
        _, head = next(rows)
        if _text(head, 2) != "Nährstoffcode / Component code":
            raise BosError("unexpected components workbook header")
        for _, cells in rows:
            code = _text(cells, 2).strip()
            if code:
                components[code] = {"code": code, "name_de": _text(cells, 3), "name_en": _text(cells, 4),
                                    "unit": _text(cells, 5), "group_de": _text(cells, 6), "group_en": _text(cells, 7)}
    return outer, data_x[0], components


def import_bls(zip_path, out_path, log=print):
    with open(zip_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    if sha != BLS_SHA256:
        log("note: SHA-256 %s differs from the known BLS 4.0 (2025) release; importing anyway" % sha)
    outer, data_name, components = parse_bls(zip_path)
    rows = xlsx_rows(outer.read(data_name))
    _, head = next(rows)
    fixed = [_text(head, i) for i in (1, 2, 3)]
    if fixed != ["BLS Code", "Lebensmittelbezeichnung", "Food name"]:
        raise BosError("unexpected BLS header: %r" % fixed)
    cols = []  # (value_col, method_col, code, unit)
    col = 4
    while True:
        h = _text(head, col)
        if h == "Hinweis" or not h:
            break
        m = re.match(r"^(\S+) (.*) \[(.+)/100g\]$", h)
        if not m or _text(head, col + 1) != m.group(1) + " Datenherkunft" or _text(head, col + 2) != m.group(1) + " Referenz":
            raise BosError("unexpected BLS column layout at column %d: %r" % (col, h))
        cols.append((col, col + 1, m.group(1), m.group(3), m.group(2)))
        col += 3
    note_col = col if _text(head, col) == "Hinweis" else None
    for _, _, code, unit, name in cols:
        components.setdefault(code, {"code": code, "name_de": name, "name_en": None, "unit": unit,
                                     "group_de": None, "group_en": None})
    missing_cols = [k for k, code in FOOD_COLUMNS.items() if code not in {c[2] for c in cols}]
    if missing_cols:
        raise BosError("BLS workbook lacks components for %s" % missing_cols)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.executescript("""
        CREATE TABLE foods (food_id TEXT PRIMARY KEY, name_de TEXT NOT NULL, name_en TEXT, category TEXT,
          kcal REAL, protein_g REAL, fat_g REAL, carbs_g REAL, fiber_g REAL, sugar_g REAL, salt_g REAL,
          note TEXT, search_key TEXT, source TEXT NOT NULL);
        CREATE TABLE nutrients (food_id TEXT NOT NULL, component TEXT NOT NULL, value REAL, unit TEXT,
          status TEXT NOT NULL, method TEXT, PRIMARY KEY (food_id, component)) WITHOUT ROWID;
        CREATE TABLE components (code TEXT PRIMARY KEY, name_de TEXT, name_en TEXT, unit TEXT,
          group_de TEXT, group_en TEXT);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    status_counts = collections.Counter()
    unknown = collections.Counter()
    food_rows, nut_rows = [], []
    seen = set()
    for rno, cells in rows:
        code = _text(cells, 1).strip()
        if not code:
            continue
        if code in seen:
            raise BosError("duplicate BLS code %s (row %d)" % (code, rno))
        seen.add(code)
        fid = "bls:" + code
        vals = {}
        for vcol, mcol, comp, unit, _ in cols:
            c = cells.get(vcol)
            value, status = None, "missing"
            if c is not None and c[0] == "n":
                value = float(c[1])
                status = "zero" if value == 0 else "numeric"
            elif c is not None:
                marker = c[1].strip().upper()
                status = MARKERS.get(marker)
                if status is None:
                    status = "unknown_marker"
                    unknown[c[1]] += 1
            status_counts[status] += 1
            vals[comp] = value
            nut_rows.append((fid, comp, value, unit, status, _text(cells, mcol) or None))
        name_de, name_en = _text(cells, 2).strip(), _text(cells, 3).strip() or None
        food_rows.append((fid, name_de, name_en, code[0],
                          *[vals.get(FOOD_COLUMNS[k]) for k in ("kcal", "protein_g", "fat_g", "carbs_g",
                                                                "fiber_g", "sugar_g", "salt_g")],
                          (_text(cells, note_col).strip() or None) if note_col else None,
                          norm_name(name_de) + " " + norm_name(name_en), "BLS 4.0"))
        if len(nut_rows) > 200000:
            con.executemany("INSERT INTO nutrients VALUES (?,?,?,?,?,?)", nut_rows)
            nut_rows = []
    con.executemany("INSERT INTO nutrients VALUES (?,?,?,?,?,?)", nut_rows)
    con.executemany("INSERT INTO foods VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", food_rows)
    con.executemany("INSERT INTO components VALUES (:code,:name_de,:name_en,:unit,:group_de,:group_en)",
                    list(components.values()))
    con.execute("CREATE INDEX idx_nutrients_component ON nutrients(component, status)")
    fts = True
    try:
        con.execute("CREATE VIRTUAL TABLE foods_fts USING fts5(food_id UNINDEXED, name_de, name_en,"
                    " tokenize = 'unicode61 remove_diacritics 2')")
        con.execute("INSERT INTO foods_fts SELECT food_id, name_de, COALESCE(name_en, '') FROM foods")
    except sqlite3.OperationalError:
        fts = False
        con.execute("CREATE INDEX idx_foods_search ON foods(search_key)")
    meta = {
        "source": "BLS 4.0", "source_file": os.path.basename(zip_path), "source_sha256": sha,
        "source_sha256_known_release": str(sha == BLS_SHA256).lower(),
        "attribution": BLS_ATTRIBUTION, "licence": "CC BY 4.0", "url": "https://blsdb.de",
        "doi": "10.25826/Data20251217-134202-0", "basis": "per 100 g edible portion",
        "imported_at": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "food_count": str(len(food_rows)), "component_count": str(len(cols)),
        "status_counts": dumps(dict(status_counts)), "fts5": str(fts).lower(),
        "missing_policy": "non-numeric source values are NULL with an explicit status; never coerced to 0",
    }
    con.executemany("INSERT INTO meta VALUES (?, ?)", list(meta.items()))
    con.commit()
    con.close()
    os.replace(tmp, out_path)
    return {"foods": len(food_rows), "components": len(cols), "status_counts": dict(status_counts),
            "unknown_markers": dict(unknown), "sha256": sha, "fts5": fts}


def cmd_foods_import(ctx, args):
    src = args.bls or os.path.join(ctx.data, "sources", "BLS_4_0_2025_DE.zip")
    if not os.path.exists(src):
        raise BosError("BLS archive not found at %s. Download BLS 4.0 from https://blsdb.de "
                       "(doi:10.25826/Data20251217-134202-0) and pass --bls PATH or place it there." % src)
    out = os.path.join(ctx.data, "foods.sqlite")
    print("importing %s -> %s (takes about a minute)" % (src, out), flush=True)
    st = import_bls(src, out)
    print("foods %d, components %d, fts5 %s" % (st["foods"], st["components"], st["fts5"]))
    print("value status: " + ", ".join("%s %d" % kv for kv in sorted(st["status_counts"].items())))
    if st["unknown_markers"]:
        print("unknown markers: %s" % st["unknown_markers"])
    print("sha256 %s%s" % (st["sha256"], " (known BLS 4.0 release)" if st["sha256"] == BLS_SHA256 else ""))
    print("attribution: " + BLS_ATTRIBUTION)
    return 0


# --------------------------------------------------------------------------------------------
# food search / calc
# --------------------------------------------------------------------------------------------

def foods_db(ctx):
    path = os.path.join(ctx.data, "foods.sqlite")
    if not os.path.exists(path):
        raise BosError("no food database at %s - run `bos.py foods-import`" % path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def search_foods(con, query, limit=10):
    key = norm_name(query)
    found = {}
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    if "foods_fts" in tables:
        tokens = [t for t in re.split(r"\W+", query) if t]
        if tokens:
            match = " ".join('"%s"*' % t.replace('"', '') for t in tokens)
            for r in con.execute("SELECT f.* FROM foods_fts JOIN foods f USING (food_id) WHERE foods_fts MATCH ?"
                                 " LIMIT 500", (match,)):
                found[r["food_id"]] = r
    if key:
        for r in con.execute("SELECT * FROM foods WHERE search_key LIKE ? LIMIT 500", ("%" + key + "%",)):
            found[r["food_id"]] = r

    def rank(r):
        de, en = norm_name(r["name_de"]), norm_name(r["name_en"])
        return (0 if de.startswith(key) or en.startswith(key) else 1 if key in de or key in en else 2,
                len(r["name_de"]), r["name_de"])
    return sorted(found.values(), key=rank)[:limit]


def cmd_food_search(ctx, args):
    con = foods_db(ctx)
    rows = search_foods(con, " ".join(args.query), args.limit)
    if args.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print("no match")
        return 1
    print("%-12s %6s %6s  %s" % ("food_id", "kcal", "prot_g", "name (per 100 g)"))
    for r in rows:
        print("%-12s %6s %6s  %s%s" % (r["food_id"], fmt_num(r["kcal"]), fmt_num(r["protein_g"], 1), r["name_de"],
                                       " / " + r["name_en"] if r["name_en"] else ""))
    return 0


def food_calc(con, items):
    totals = {k: None for k in CALC_NUTRIENTS}
    lines, missing, unknown = [], [], []
    for it in items:
        fid, g = it.get("food_id"), it.get("g")
        if not isinstance(fid, str) or not is_num(g) or g < 0:
            raise BosError("each item needs food_id (string) and g (number >= 0): %r" % it)
        if not fid.startswith("bls:") and ":" not in fid:
            fid = "bls:" + fid
        r = con.execute("SELECT * FROM foods WHERE food_id = ?", (fid,)).fetchone()
        if r is None:
            unknown.append(fid)
            continue
        line = {"food_id": fid, "name": r["name_de"], "g": g}
        for k in CALC_NUTRIENTS:
            v = r[k]
            if v is None:
                comp = FOOD_COLUMNS[k]
                st = con.execute("SELECT status FROM nutrients WHERE food_id = ? AND component = ?", (fid, comp)).fetchone()
                missing.append({"food_id": fid, "name": r["name_de"], "nutrient": k,
                                "status": st["status"] if st else "missing"})
                line[k] = None
            else:
                line[k] = v * g / 100
                totals[k] = (totals[k] or 0.0) + line[k]
        lines.append(line)
    return {"items": lines, "totals": totals, "missing": missing, "unknown": unknown}


def cmd_food_calc(ctx, args):
    try:
        items = json.loads(args.items)
    except json.JSONDecodeError as e:
        raise BosError("items must be a JSON list: %s" % e)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise BosError("items must be a JSON list of {food_id, g}")
    res = food_calc(foods_db(ctx), items)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    for ln in res["items"]:
        print("%6sg %-40s " % (fmt_num(ln["g"], 1), ln["name"][:40]) +
              " ".join("%s %s" % (k.replace("_g", ""), fmt_num(ln[k], 1)) for k in CALC_NUTRIENTS))
    t = res["totals"]
    print("total: %s kcal, protein %s g, carbs %s g, fat %s g, fiber %s g" % tuple(
        fmt_num(t[k], 1) for k in CALC_NUTRIENTS))
    if res["missing"]:
        print("incomplete (not counted): " + "; ".join("%s %s (%s)" % (m["name"], m["nutrient"], m["status"])
                                                     for m in res["missing"]))
    if res["unknown"]:
        print("unknown food_id: " + ", ".join(res["unknown"]))
        return 1
    return 0


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="bos.py", description="body-os CLI (see docs/DATA_FORMAT.md)")
    p.add_argument("--me", help="instance folder (default: <repo>/me)")
    p.add_argument("--data", help="derived data folder (default: <repo>/data)")
    p.add_argument("--today", help="pretend today is DATE (YYYY-MM-DD) for summary/pantry/build")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create me/ from templates/me, git init it, enable engine hooks")
    sub.add_parser("doctor", help="check privacy guards and data validity")

    for name, hlp in (("log", "append health event(s) to me/log/YYYY/YYYY-MM.jsonl"),
                      ("pantry-log", "append pantry event(s) to me/pantry/pantry.jsonl")):
        sp = sub.add_parser(name, help=hlp, description=hlp + ". Input: a JSON object or array as argument, "
                            "--file, or stdin. Missing id/ts/src are filled (ts = now, local offset; naive "
                            "timestamps get the local offset).")
        sp.add_argument("json", nargs="?", help="JSON object or array ('-' or omitted = stdin)")
        sp.add_argument("--file", help="read JSON from file")
        sp.add_argument("--dry-run", action="store_true", help="validate and print, do not write")

    sub.add_parser("validate", help="validate all jsonl files in me/")

    sp = sub.add_parser("summary", help="aggregated per-day table and period averages (for agents)")
    sp.add_argument("--days", type=int, help="number of days ending --to/today (default 7)")
    sp.add_argument("--from", dest="frm", help="start date YYYY-MM-DD")
    sp.add_argument("--to", help="end date YYYY-MM-DD (default today)")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--notes", action="store_true", help="include free-text notes and symptom descriptions")

    sp = sub.add_parser("pantry", help="current pantry state, most urgent first")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--all", action="store_true", help="include gone items")

    sub.add_parser("build", help="rebuild data/body-os.sqlite and datasette metadata")
    sp = sub.add_parser("dash", help="build, then serve the Datasette dashboard on 127.0.0.1")
    sp.add_argument("--port", type=int, default=8001)

    sp = sub.add_parser("foods-import", help="build data/foods.sqlite from the BLS 4.0 archive",
                        description="Build data/foods.sqlite from BLS 4.0. " + BLS_HELP)
    sp.add_argument("--bls", help=BLS_HELP)

    sp = sub.add_parser("food", help="food lookup: search / calc")
    fsub = sp.add_subparsers(dest="food_cmd", required=True)
    fs = fsub.add_parser("search", help="search foods by German or English name")
    fs.add_argument("query", nargs="+")
    fs.add_argument("--limit", type=int, default=10)
    fs.add_argument("--json", action="store_true")
    fc = fsub.add_parser("calc", help="sum nutrients for a JSON list of {food_id, g}")
    fc.add_argument("items", help='e.g. \'[{"food_id": "bls:C133000", "g": 60}]\'')
    fc.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    handlers = {"init": cmd_init, "doctor": cmd_doctor, "log": cmd_log, "pantry-log": cmd_pantry_log,
                "validate": cmd_validate, "summary": cmd_summary, "pantry": cmd_pantry, "build": cmd_build,
                "dash": cmd_dash, "foods-import": cmd_foods_import}
    try:
        ctx = Ctx(args.me, args.data, args.today)
        if args.cmd == "food":
            return cmd_food_search(ctx, args) if args.food_cmd == "search" else cmd_food_calc(ctx, args)
        return handlers[args.cmd](ctx, args)
    except BosError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
