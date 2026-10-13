#!/usr/bin/env python3
"""bos - body-os command line tool (Python 3.9+, standard library only).

Spec: docs/DATA_FORMAT.md and docs/ARCHITECTURE.md. Personal data lives in me/ (or --me DIR);
in household mode in each member's folder (--profile ID), with the shared kitchen in household/
(or --household DIR). Derived databases live in data/ (or --data DIR). Run `bos.py <command> -h` for details.
"""

import argparse
import collections
import datetime as dt
import hashlib
import hmac
import io
import ipaddress
import json
import os
import re
import secrets
import socket
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


# --------------------------------------------------------------------------------------------
# Household mode (docs/ARCHITECTURE.md): household/household.json lists members whose instance
# folders hold personal data; household/ holds the shared kitchen (pantry, cookbook, shopping list).
# --------------------------------------------------------------------------------------------

MEMBER_COLORS = ("blue", "orange", "aqua", "yellow", "magenta", "green", "violet", "red")
PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
SHARED_FILES = ("pantry/pantry.jsonl", "recipes/cookbook.jsonl", "pantry/shopping-list.md")
SHARED_SETTINGS = ("household", "kitchen", "pantry", "cooking")
SINGLE_PROFILE = "me"
DEFAULT_HOUSEHOLD = os.path.join(ROOT, "household")  # module-level so tests can point it elsewhere


def read_json_file(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json_file(path, obj, mode=None):
    """Write JSON atomically (temp file + rename); mode e.g. 0o600 for secrets."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode if mode is not None else 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


def initials(name):
    parts = [p for p in re.split(r"[\s._-]+", str(name or "").strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def member_path_ok(p):
    """Instance paths are relative, normalised and never point into household/ or hidden dirs."""
    if not isinstance(p, str) or not p.strip() or p.startswith("/") or "\\" in p or ":" in p:
        return False
    segs = p.strip("/").split("/")
    return (all(s and s not in (".", "..") and not s.startswith(".") for s in segs)
            and segs[0].lower() not in ("household", "data", "tools", "examples", "templates"))


def household_errors(hh):
    if not isinstance(hh, dict):
        return ["household.json is not a JSON object"]
    members = hh.get("members")
    if not isinstance(members, list):
        return ["'members' must be a list"]
    errs, ids, paths = [], set(), set()
    for i, m in enumerate(members):
        if not isinstance(m, dict):
            errs.append("members[%d] is not an object" % i)
            continue
        mid = m.get("id")
        if not isinstance(mid, str) or not PROFILE_ID_RE.match(mid):
            errs.append("members[%d].id must match %s" % (i, PROFILE_ID_RE.pattern))
        elif mid in ids:
            errs.append("duplicate member id %r" % mid)
        ids.add(mid)
        if not isinstance(m.get("name"), str) or not m["name"].strip():
            errs.append("members[%d].name missing" % i)
        if m.get("color") not in MEMBER_COLORS:
            errs.append("members[%d].color must be one of %s" % (i, "/".join(MEMBER_COLORS)))
        if not member_path_ok(m.get("path")):
            errs.append("members[%d].path must be a relative folder like people/<id>" % i)
        elif any(m["path"].strip("/") == q or m["path"].strip("/").startswith(q + "/") or q.startswith(
                m["path"].strip("/") + "/") for q in paths):
            errs.append("member path %r overlaps another member's folder" % m["path"])
        else:
            paths.add(m["path"].strip("/"))
        if not isinstance(m.get("consent"), bool):
            errs.append("members[%d].consent must be true/false" % i)
    dm = hh.get("default_member")
    if dm is not None and dm not in ids:
        errs.append("default_member %r is not a member" % dm)
    return errs


def merge_settings(member, shared):
    """Member settings with the household's shared keys on top (household wins for the kitchen)."""
    s = dict(member)
    for k in SHARED_SETTINGS:
        if k in shared:
            s[k] = shared[k]
    if isinstance(shared.get("costs"), dict):
        s["costs"] = dict(member.get("costs") if isinstance(member.get("costs"), dict) else {}, **shared["costs"])
    if shared.get("language"):
        s["language"] = shared["language"]
    if shared.get("timezone") and not member.get("timezone"):
        s["timezone"] = shared["timezone"]
    return s


def _same_path(a, b):
    return os.path.realpath(a) == os.path.realpath(b)


class Ctx:
    """Resolved paths and settings for one invocation.

    Single-user: me/ (or --me DIR) holds everything. Household mode (household/household.json
    exists, or --household DIR): the profile's instance folder holds personal data, household/
    the shared kitchen. Member paths are relative to the folder that contains household/ (the
    engine root). An explicit --me without --household stays single-user."""

    def __init__(self, me=None, data=None, today=None, household=None, profile=None):
        self.root = ROOT
        self.opts = {"me": me, "data": data, "today": today, "household": household}
        self.data = os.path.abspath(data) if data else os.path.join(ROOT, "data")
        if household:
            hdir = os.path.abspath(household)
        elif me:
            # an explicit --me stays single-user unless it is a registered member of <repo>/household
            # (then the consent gate and the shared kitchen apply as with --profile)
            dflt = DEFAULT_HOUSEHOLD
            hh = read_json_file(os.path.join(dflt, "household.json"))
            hdir = dflt if not household_errors(hh) and any(_same_path(
                os.path.join(os.path.dirname(dflt), *m["path"].strip("/").split("/")), me) for m in hh["members"]) else None
        else:
            hdir = DEFAULT_HOUSEHOLD
        self.household_dir = hdir
        self.base = os.path.dirname(hdir) if hdir else ROOT
        self.household = None
        if hdir and os.path.exists(os.path.join(hdir, "household.json")):
            hh = read_json_file(os.path.join(hdir, "household.json"))
            errs = household_errors(hh)
            if errs:
                raise BosError("invalid %s: %s" % (os.path.join(hdir, "household.json"), "; ".join(errs)))
            self.household = hh
        self.member = None
        if self.household:
            members = self.household["members"]
            if profile:
                self.member = next((m for m in members if m["id"] == profile), None)
                if self.member is None:
                    raise BosError("unknown profile %r - see `bos.py profile list`" % profile)
                if me and not _same_path(me, self.member_dir(self.member)):
                    raise BosError("--me and --profile point to different folders")
            elif me:
                self.member = next((m for m in members if _same_path(self.member_dir(m), me)), None)
            else:
                dm = self.household.get("default_member")
                self.member = next((m for m in members if (m["id"] == dm if dm else m["path"].strip("/") == "me")), None)
            self.me = self.member_dir(self.member) if self.member else (
                os.path.abspath(me) if me else os.path.join(self.base, "me"))
        else:
            if profile and profile != SINGLE_PROFILE:
                raise BosError("no household (household/household.json) - --profile %r needs "
                               "`bos.py household init` first" % profile)
            self.me = os.path.abspath(me) if me else os.path.join(self.base, "me")
        ms = read_json_file(os.path.join(self.me, "settings.json"), {})
        self.member_settings = ms if isinstance(ms, dict) else {}
        hs = read_json_file(os.path.join(hdir, "settings.json"), {}) if self.household else {}
        self.household_settings = hs if isinstance(hs, dict) else {}
        if self.member and not self.member["consent"]:  # nothing personal before consent
            ms = {k: self.member_settings[k] for k in ("language", "timezone") if k in self.member_settings}
        else:
            ms = self.member_settings
        self.settings = merge_settings(ms, self.household_settings)
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

    def member_dir(self, m):
        return os.path.join(self.base, *m["path"].strip("/").split("/"))

    @property
    def consent(self):
        """False only for a household member who has not consented / not been onboarded yet."""
        if self.member:
            return bool(self.member["consent"])
        return not self.household  # household mode without a selected member: nothing personal

    @property
    def profile_id(self):
        return self.member["id"] if self.member else (None if self.household else SINGLE_PROFILE)

    def members(self):
        """Public member list; single-user mode yields one synthetic member 'me'."""
        if self.household:
            return [{"id": m["id"], "name": m["name"], "color": m["color"], "consent": m["consent"],
                     "initials": initials(m["name"]), "path": m["path"]} for m in self.household["members"]]
        de = str(self.settings.get("language") or "").startswith("de")
        name = self.settings.get("display_name") or ("Ich" if de else "Me")
        color = self.settings.get("color") if self.settings.get("color") in MEMBER_COLORS else "blue"
        return [{"id": SINGLE_PROFILE, "name": name, "color": color, "consent": True, "initials": initials(name),
                 "path": os.path.relpath(self.me, self.base)}]

    def profile_json(self):
        pid = self.profile_id
        m = next((m for m in self.members() if m["id"] == pid), None)
        return {k: m[k] for k in ("id", "name", "color", "consent", "initials")} if m else None

    def for_profile(self, pid=None):
        """A fresh Ctx for another member (re-reads household.json and settings)."""
        o = self.opts
        if pid is None:
            return Ctx(o["me"], o["data"], o["today"], o["household"])
        if self.household:
            return Ctx(None, o["data"], o["today"], self.household_dir, pid)
        return Ctx(self.me, o["data"], o["today"], o["household"], pid)

    def shared_path(self, rel):
        """Kitchen files: household/ when it has them (or the instance lacks them), else the instance."""
        mine = os.path.join(self.me, *rel.split("/"))
        if not self.household:
            return mine
        shared = os.path.join(self.household_dir, *rel.split("/"))
        return shared if os.path.exists(shared) or not os.path.exists(mine) else mine

    def rel(self, path):
        """Path for messages: relative to the instance, or to the engine root when outside it."""
        inside = os.path.realpath(path).startswith(os.path.realpath(self.me) + os.sep)
        return os.path.relpath(path, self.me if inside else self.base)

    @property
    def log_dir(self):
        return os.path.join(self.me, "log")

    @property
    def pantry_path(self):
        return self.shared_path("pantry/pantry.jsonl")

    @property
    def cookbook_path(self):
        return self.shared_path("recipes/cookbook.jsonl")

    @property
    def shopping_list_path(self):
        return self.shared_path("pantry/shopping-list.md")

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
    _check_num(ev, "price_eur", errs, 0, 100000)
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


def require_consent(ctx):
    if ctx.household and not ctx.member:
        raise BosError("household mode: no member selected for %s - pass --profile ID (bos.py profile list) "
                       "or set default_member in household.json" % ctx.me)
    if not ctx.consent:
        raise BosError("member %r has not consented / not onboarded yet - nothing written. Run their own "
                       "interview first (interview/README.md), then `bos.py profile consent %s`"
                       % (ctx.member["name"], ctx.member["id"]))


def cmd_log(ctx, args):
    require_consent(ctx)
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
    require_consent(ctx)
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
    print("%s %d event(s) -> %s" % ("would append" if args.dry_run else "appended", len(events),
                                    ctx.rel(ctx.pantry_path)), file=sys.stderr)
    return 0


# --------------------------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------------------------

def validate_all(ctx):
    """Return list of (relative path, line, message)."""
    problems = []
    rel = ctx.rel
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
        was_gone = st["gone"]
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
        if st["gone"] and not was_gone:
            st["gone_at"] = (ev.get("ts") or "")[:10]
        elif not st["gone"]:
            st.pop("gone_at", None)
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
# dashboard (local web UI: tools/dashboard/ + GET /api/data, read-only, 127.0.0.1 only)
# --------------------------------------------------------------------------------------------

DASHBOARD_DIR = os.path.join(ROOT, "tools", "dashboard")
DASHBOARD_PERIODS = ("14", "30", "90", "all")
DASHBOARD_TABS = ("today", "body", "nutrition", "kitchen", "sleep", "substances", "training", "journal")
DASHBOARD_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                   ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                   ".ico": "image/x-icon", ".woff2": "font/woff2", ".webmanifest": "application/manifest+json"}
DASHBOARD_CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                 "connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'; "
                 "frame-ancestors 'none'")
DASHBOARD_PANTRY_FIELDS = ("item_id", "name", "status", "days_left", "expires", "date_kind", "check_hint",
                           "storage", "remaining", "unit", "opened", "expires_est", "category")
DASHBOARD_TRAINING_PLAN = 4
DASHBOARD_CHECKLIST = ("weight", "sleep", "meals>=2", "checkin")
DASHBOARD_TEXT_MAX = 512 * 1024
REVIEW_FILE_RE = re.compile(r"^\d{4}-(W\d{2}|\d{2})\.md$")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
ENDURANCE_KINDS = ("run", "bike")
CIRCUMFERENCES = ("waist_cm", "arm_cm", "chest_cm", "thigh_cm")
VITALS = ("resting_hr", "hrv_ms", "vo2max")
MEASURE_GROUPS = {"circumferences": ("waist_cm", "arm_cm", "chest_cm", "thigh_cm", "hip_cm", "neck_cm")}
CHECK_ALIASES = {"meals": "meal", "checkins": "checkin", "weights": "weight", "drinks": "drink",
                 "trainings": "training", "notes": "note"}


def _r(v, nd=2):
    return round(v, nd) if is_num(v) else v


def _local_dt(ts):
    """Wall-clock time as written in the timestamp (naive), like local_day()."""
    return parse_ts(ts).replace(tzinfo=None)


def _epley(kg, reps):
    if not is_num(kg) or not is_int(reps) or reps <= 0:
        return None
    return kg if reps == 1 else kg * (1 + reps / 30.0)


def _dict(v):
    return v if isinstance(v, dict) else {}


def _list(v):
    return v if isinstance(v, list) else []


def _day_or_none(s):
    try:
        return parse_date(s)
    except (ValueError, TypeError, IndexError):
        return None


def _minutes(t):
    return t.hour * 60 + t.minute


def _hm_of(minutes):
    minutes = int(round(minutes)) % 1440
    return "%02d:%02d" % (minutes // 60, minutes % 60)


def _band(v):
    """Number or [lo, hi] -> [lo, hi|None]; anything else -> None."""
    if is_num(v):
        return [v, None]
    if isinstance(v, list) and v and is_num(v[0]):
        return [v[0], v[1] if len(v) > 1 and is_num(v[1]) else None]
    return None


def _read_text(path):
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > DASHBOARD_TEXT_MAX:
            return None
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def training_category(kind):
    return "strength" if kind == "strength" else "endurance" if kind in ENDURANCE_KINDS else "other"


def settings_phases(settings):
    """Valid phases from settings, sorted by start: {id, name, from, to (date|None), focus, targets}."""
    out = []
    for p in _list(settings.get("phases")):
        frm = _day_or_none(_dict(p).get("from"))
        if not frm:
            continue
        name = p.get("name") or p.get("id") or frm.isoformat()
        out.append({"id": str(p.get("id") or slug(name)), "name": str(name), "from": frm,
                    "to": _day_or_none(p.get("to")), "focus": p.get("focus"), "targets": _dict(p.get("targets"))})
    out.sort(key=lambda p: p["from"])
    return out


def current_phase(phases, day):
    cur = [p for p in phases if p["from"] <= day and (p["to"] is None or day <= p["to"])]
    return cur[-1] if cur else None


def phase_json(p, today):
    if not p:
        return None
    return {"id": p["id"], "name": p["name"], "from": p["from"].isoformat(),
            "to": p["to"].isoformat() if p["to"] else None, "focus": p["focus"], "targets": p["targets"],
            "day": (today - p["from"]).days + 1, "of": (p["to"] - p["from"]).days + 1 if p["to"] else None}


def upcoming_phase_json(phases, today):
    """The next phase that has not started yet, marked as upcoming (for a banner before the plan begins)."""
    nxt = [p for p in phases if p["from"] > today]
    if not nxt:
        return None
    out = phase_json(nxt[0], today)
    out.update(upcoming=True, starts_in=(nxt[0]["from"] - today).days, day=0)
    return out


def settings_decisions(settings, today):
    out = []
    for d in _list(settings.get("decisions")):
        if not _dict(d).get("title"):
            continue
        day = _day_or_none(d.get("date"))
        out.append({"date": day.isoformat() if day else None, "title": str(d["title"]),
                    "status": "done" if d.get("status") == "done" else "open", "note": d.get("note"),
                    "days_left": (day - today).days if day else None})
    out.sort(key=lambda d: (d["date"] is None, d["date"] or ""))
    return out


def next_decision(decisions):
    open_ = [d for d in decisions if d["status"] == "open"]
    upcoming = [d for d in open_ if d["days_left"] is not None and d["days_left"] >= 0]
    return (upcoming or open_ or [None])[0]


def review_files(me):
    """Review markdown files in me/reviews/ matching the whitelist, newest period first."""
    rdir = os.path.realpath(os.path.join(me, "reviews"))
    try:
        names = [n for n in os.listdir(rdir) if REVIEW_FILE_RE.match(n)
                 and os.path.dirname(os.path.realpath(os.path.join(rdir, n))) == rdir
                 and os.path.isfile(os.path.join(rdir, n))]
    except OSError:
        return []

    def end(n):
        y, rest = int(n[:4]), n[5:-3]
        try:
            if rest.startswith("W"):
                return dt.date.fromisocalendar(y, int(rest[1:]), 7)
            m = int(rest)
            return dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1)
        except ValueError:
            return dt.date(y, 1, 1)
    return sorted(names, key=lambda n: (end(n), n), reverse=True)


def review_text(me, name):
    """Markdown of me/reviews/<name>, or None. Only whitelisted names; no traversal, no symlink escape."""
    if not isinstance(name, str) or not REVIEW_FILE_RE.match(name):
        return None
    rdir = os.path.realpath(os.path.join(me, "reviews"))
    full = os.path.realpath(os.path.join(rdir, name))
    if os.path.dirname(full) != rdir:
        return None
    return _read_text(full)


def review_title(text, name):
    for line in (text or "").splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if m:
            return m.group(1)
    return name[:-3]


def extract_focus(text):
    """First list item or paragraph under a heading containing 'Fokus'/'Focus'; else a 'Focus: …' line."""
    lines = (text or "").splitlines()
    inside, para = False, []
    for line in lines:
        s = line.strip()
        if s.startswith("#"):
            if inside:
                break
            inside = bool(re.search(r"fokus|focus", s, re.I))
            continue
        if not inside:
            continue
        if not s:
            if para:
                break
            continue
        m = re.match(r"^(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)$", s)
        if m and not para:
            return m.group(1).strip() or None
        para.append(s)
    if para:
        return " ".join(para)
    for line in lines:
        m = re.match(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?[^:\n]*(?:fokus|focus)[^:\n]*?:\s*(?:\*\*|__)?\s*(.+)$", line, re.I)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def _measure_due(rule, mdays, today):
    """Due-state of one measurement rule for today, or None when not scheduled today."""
    rule = str(rule).strip().lower()
    monday = today - dt.timedelta(days=today.weekday())
    m = re.match(r"^weekly:([a-z]{3})", rule)
    if m:
        if WEEKDAYS[today.weekday()] != m.group(1):
            return None
        if today in mdays:
            return {"status": "done"}
        recent = any(today - dt.timedelta(days=6) <= d < today for d in mdays)
        return {"status": "done" if recent else "due"}
    m = re.match(r"^monthly:first-([a-z]{3})", rule)
    if m and m.group(1) in WEEKDAYS:
        first = today.replace(day=1)
        first += dt.timedelta(days=(WEEKDAYS.index(m.group(1)) - first.weekday()) % 7)
        if today != first:
            return None
        logged = any((d.year, d.month) == (today.year, today.month) for d in mdays)
        return {"status": "done" if logged else "due"}
    m = re.match(r"^(\d+)x-week$", rule)
    if m:
        n, count = int(m.group(1)), sum(1 for d in mdays if monday <= d <= today)
        return {"status": "done" if count >= n else "open", "count": count, "of": n}
    return None


def _training_matches(ev, what):
    what = str(what).lower()
    return what in (ev.get("kind"), training_category(ev.get("kind")), str(ev.get("plan") or "").lower())


def training_due(settings, sessions_by_day, today):
    """Scheduled training for today ('sat|sun' = either day) and whether it is done; plus the next one."""
    sched = _dict(_dict(settings.get("training")).get("schedule"))
    monday = today - dt.timedelta(days=today.weekday())
    due, upcoming = [], []
    for key, what in sched.items():
        days = [x.strip().lower()[:3] for x in str(key).split("|") if x.strip().lower()[:3] in WEEKDAYS]
        if not days:
            continue
        idx = [WEEKDAYS.index(x) for x in days]
        if today.weekday() in idx:
            done = None
            for i in idx:
                d = monday + dt.timedelta(days=i)
                if d <= today and any(_training_matches(e, what) for e in sessions_by_day.get(d, [])):
                    done = d
            due.append({"what": str(what), "days": str(key), "done": done is not None,
                        "done_day": done.isoformat() if done else None})
        for off in range(1, 8):
            d = today + dt.timedelta(days=off)
            if d.weekday() in idx:
                upcoming.append((d, str(what)))
                break
    upcoming.sort()
    nxt = {"day": upcoming[0][0].isoformat(), "what": upcoming[0][1]} if upcoming else None
    return due, nxt


COST_CATEGORIES = ("groceries", "out", "tobacco", "cannabis", "alcohol", "coffee")
COST_KEYS = ("tobacco_eur_per_g", "tobacco_g_per_use", "cannabis_eur_per_g", "cannabis_g_per_use",
             "alcohol_eur_per_unit", "coffee_eur_per_cup_home")
CANNABIS_KINDS = ("joint", "cannabis_vape")


def cost_settings(settings):
    """settings.costs with every known key present (None = not set)."""
    c = _dict(_dict(settings).get("costs"))
    out = {k: c[k] if is_num(c.get(k)) and c[k] >= 0 else None for k in COST_KEYS}
    out["currency"] = c["currency"] if isinstance(c.get("currency"), str) and c["currency"] else "EUR"
    return out


def event_costs(ev, cs):
    """Cost parts of one log event: [(category, eur or None if unknown, estimated)].

    meal/drink `price_eur` = paid (eaten out, on the go); home-cooked meals cost nothing here (groceries
    are counted at purchase). Substances: `price_eur` wins, else estimated from settings.costs."""
    t, price = ev.get("type"), ev.get("price_eur") if is_num(ev.get("price_eur")) else None
    if t == "meal":
        return [("out", price, False)] if price is not None else []
    if t == "drink":
        units = ev.get("alcohol_units") if is_num(ev.get("alcohol_units")) else 0
        cat = "alcohol" if ev.get("kind") == "alcohol" or units > 0 else "coffee" if ev.get("kind") == "coffee" else "out"
        if price is not None:
            return [(cat, price, False)]
        if cat == "alcohol" and units > 0:
            p = cs["alcohol_eur_per_unit"]
            return [("alcohol", units * p if p is not None else None, True)]
        if cat == "coffee":
            return [("coffee", cs["coffee_eur_per_cup_home"], True)]
        return []
    if t != "substance":
        return []
    kind, n = ev.get("kind"), ev.get("count") if is_int(ev.get("count")) and ev["count"] > 0 else 1
    g = ev.get("g") if is_num(ev.get("g")) else None
    if price is not None:
        cannabis = kind in CANNABIS_KINDS or (kind == "other" and not ev.get("tobacco"))
        return [("cannabis" if cannabis else "tobacco", price, False)]
    parts = []

    def est(cat, grams):
        p = cs[cat + "_eur_per_g"]
        parts.append((cat, grams * p if grams is not None and p is not None else None, True))
    tob_use = cs["tobacco_g_per_use"] * n if cs["tobacco_g_per_use"] is not None else None
    can_use = cs["cannabis_g_per_use"] * n if cs["cannabis_g_per_use"] is not None else None
    if kind == "cigarette":
        est("tobacco", g if g is not None else tob_use)
    elif kind == "joint":
        if ev.get("tobacco"):
            est("tobacco", tob_use)
        est("cannabis", g if g is not None else can_use)
    elif kind == "cannabis_vape":
        est("cannabis", g if g is not None else can_use)
    return parts


def cost_days(ctx, events, pevents, cs):
    """{date: {category: {"eur", "est", "unknown"}}} over all history (log events + pantry purchases)."""
    out = collections.defaultdict(dict)

    def add(day, cat, eur, est):
        c = out[day].setdefault(cat, {"eur": 0.0, "est": False, "unknown": 0})
        if eur is None:
            c["unknown"] += 1
        else:
            c["eur"] += eur
            c["est"] = c["est"] or est
    for e in events:
        for cat, eur, est in event_costs(e, cs):
            add(event_day(e), cat, eur, est)
    for e in pevents:
        d = _day_or_none(e.get("ts")) if e.get("type") == "purchase" else None
        for it in _list(e.get("items")) if d else []:
            if isinstance(it, dict):
                add(d, "groceries", it["price_eur"] if is_num(it.get("price_eur")) else None, False)
    return out


def cost_sum(cdays, days_, cats=COST_CATEGORIES):
    """Per-category totals over days: {cat: {"eur", "est", "unknown", "any"}}."""
    tot = {c: {"eur": 0.0, "est": False, "unknown": 0, "any": False} for c in cats}
    for d in days_:
        for c, v in cdays.get(d, {}).items():
            if c in tot:
                t = tot[c]
                t["eur"] += v["eur"]
                t["est"] = t["est"] or v["est"]
                t["unknown"] += v["unknown"]
                t["any"] = True
    for t in tot.values():
        t["eur"] = _r(t["eur"])
    return tot



def _period_counts(events, days):
    """Substance/tobacco totals and logged-day count for a list of days (for period deltas)."""
    daily = daily_aggregates(events, days)
    rows = [daily[d] for d in days]
    logged = [r for r in rows if any(r["_events"].values())]
    meal_days = [r for r in rows if r["meals"]]
    return {"from": days[0].isoformat(), "to": days[-1].isoformat(), "days": len(days),
            "days_logged": len(logged), "substance_n": sum(r["substance_n"] for r in rows),
            "tobacco_n": sum(r["tobacco_n"] for r in rows),
            "protein_g_per_day": _r(_mean([r["protein_g"] for r in meal_days]), 1),
            "sleep_h": _r(_mean([r["sleep_h"] for r in rows]))}


def _mean_n(xs):
    xs = [x for x in xs if is_num(x)]
    return {"mean": _r(statistics.mean(xs)) if xs else None, "n": len(xs)}


def dashboard_data(ctx, days="30"):
    """JSON-ready dict for the local dashboard, grouped by tab. days: 14/30/90 or 'all' (str or int).

    Shared per-day rows live in `days`; everything a single tab needs lives in `tabs.<tab>`."""
    key = str(days)
    if key not in DASHBOARD_PERIODS:
        raise BosError("days must be one of %s" % "/".join(DASHBOARD_PERIODS))
    settings = ctx.settings if isinstance(ctx.settings, dict) else {}
    to = ctx.today
    # a member without consent gets no personal data at all (the kitchen stays household-wide)
    events = [e for e in (ctx.log_events() if ctx.consent else []) if event_day(e) is not None and event_day(e) <= to]
    if key == "all":
        seen = [event_day(e) for e in events]
        frm = min(seen) if seen else to - dt.timedelta(days=13)
    else:
        frm = to - dt.timedelta(days=int(key) - 1)
    days_ = [frm + dt.timedelta(days=i) for i in range((to - frm).days + 1)]
    wanted = set(days_)
    by_day = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in events:
        by_day[event_day(e)][e.get("type")].append(e)
    all_days = sorted(by_day)
    daily = daily_aggregates(events, days_)
    phases = settings_phases(settings)
    phase_now = current_phase(phases, to)
    modules = [m for m in _list(settings.get("modules")) if isinstance(m, str)]

    weights = collections.defaultdict(list)  # same rule as weight_trend(), computed once
    for e in events:
        if e.get("type") == "weight" and is_num(e.get("kg")):
            weights[event_day(e)].append(e["kg"])

    def trend(d):
        ws = [w for i in range(7) for w in weights.get(d - dt.timedelta(days=i), [])]
        return statistics.mean(ws) if ws else None

    def tobacco_of(d):
        return sum(e.get("count") or 1 for e in by_day.get(d, {}).get("substance", []) if e.get("tobacco"))

    def is_logged(d):
        return d in by_day and any(by_day[d].values())

    # ---------------------------------------------------------------- shared per-day rows
    day_rows, trig_period, kinds = [], collections.Counter(), collections.Counter()
    for d in days_:
        r = daily[d]
        g = r["_events"]
        trig = collections.Counter()
        for e in g["substance"]:
            trig[e.get("trigger") or "?"] += e.get("count") or 1
        trig_period.update(trig)
        kinds.update(r["substances"])
        subs = sorted(g["substance"], key=lambda e: e["ts"])
        day_rows.append({
            "day": d.isoformat(), "logged": any(g.values()),
            "weight_kg": r["weight_kg"], "weight_7d": _r(trend(d), 3),
            "sleep_h": _r(r["sleep_h"]), "sleep_quality": _r(r["sleep_quality"]), "wakeups": r["wakeups"],
            "meals": r["meals"], "meals_missing_kcal": r["meals_missing_kcal"],
            "kcal": _r(r["kcal"], 1), "protein_g": _r(r["protein_g"], 1),
            "carbs_g": _r(_sum_known([e.get("carbs_g") for e in g["meal"]]), 1),
            "fat_g": _r(_sum_known([e.get("fat_g") for e in g["meal"]]), 1),
            "water_ml": r["water_ml"], "caffeine_n": r["caffeine_n"], "last_caffeine": r["last_caffeine"],
            "alcohol_units": _r(r["alcohol_units"]), "substance_n": r["substance_n"], "tobacco_n": r["tobacco_n"],
            "triggers": dict(trig.most_common()), "first_substance": hhmm(subs[0]["ts"]) if subs else None,
            "last_substance": r["last_substance"], "training_n": r["training_n"], "training_min": r["training_min"],
            "energy": _r(r["energy"]), "mood": _r(r["mood"]), "stress": _r(r["stress"]),
        })

    previous = None
    if key != "all":
        n = len(days_)
        previous = _period_counts(events, [frm - dt.timedelta(days=n - i) for i in range(n)])

    # ---------------------------------------------------------------- measures (all history, sorted)
    by_metric = collections.defaultdict(list)
    for e in sorted((e for e in events if e.get("type") == "measure"), key=_sort_key_ts):
        m, day = e.get("metric"), event_day(e).isoformat()
        if m == "bp" and is_num(e.get("sys")) and is_num(e.get("dia")):
            by_metric["bp"].append({"day": day, "sys": e["sys"], "dia": e["dia"], "pulse": e.get("pulse"),
                                    "category": bp_category(e["sys"], e["dia"])})
        elif isinstance(m, str) and is_num(e.get("value")):
            by_metric[m].append({"day": day, "value": e["value"], "unit": e.get("unit")})

    def series(metric):
        pts = [p for p in by_metric.get(metric, []) if dt.date.fromisoformat(p["day"]) in wanted]
        last = collections.OrderedDict((p["day"], p) for p in pts)  # one point per day (latest)
        allp = by_metric.get(metric, [])
        return {"points": list(last.values()), "latest": allp[-1] if allp else None,
                "previous": allp[-2] if len(allp) > 1 else None}

    cs = cost_settings(settings)
    pevents = load_events(ctx.pantry_path)
    cdays = cost_days(ctx, events, pevents, cs)

    # ---------------------------------------------------------------- today
    t = daily_aggregates(events, [to])[to]
    tg = t["_events"]
    checklist = []
    for item in _list(settings.get("checklist")) or list(DASHBOARD_CHECKLIST):
        m = re.match(r"^\s*([a-z_]+)\s*(?:>=\s*(\d+))?\s*$", str(item))
        if not m:
            continue
        typ = CHECK_ALIASES.get(m.group(1), m.group(1))
        if typ not in LOG_TYPES:
            continue
        need, n = int(m.group(2) or 1), len(tg[typ])
        value = None
        if typ == "weight" and n:
            value = t["weight_kg"]
        elif typ == "sleep" and t["sleep_h"] is not None:
            value = _r(t["sleep_h"], 1)
        checklist.append({"key": m.group(1), "type": typ, "min": need, "n": n, "done": n >= need, "value": value})
    subs_today = None
    if "substances" in modules or any(e.get("type") == "substance" for e in events):
        subs_today = {"n": t["substance_n"], "tobacco_n": t["tobacco_n"], "last": t["last_substance"]}

    sessions_by_day = {d: by_day[d]["training"] for d in all_days if by_day[d]["training"]}
    train_due, train_next = training_due(settings, sessions_by_day, to)
    measure_due = []
    for metric, rule in _dict(settings.get("measurements")).items():
        names = MEASURE_GROUPS.get(metric, (metric,))
        mdays = {dt.date.fromisoformat(p["day"]) for nm in names for p in by_metric.get(nm, [])}
        st = _measure_due(rule, mdays, to)
        if st:
            measure_due.append(dict(st, metric=metric, rule=str(rule),
                                    last=max(mdays).isoformat() if mdays else None))
    reviews = review_files(ctx.me) if ctx.consent else []
    review_due = None
    rv_day = str(_dict(settings.get("reviews")).get("weekly") or "").lower()[:3]
    if rv_day in WEEKDAYS and WEEKDAYS[to.weekday()] == rv_day:
        y, w, _ = to.isocalendar()
        fname = "%04d-W%02d.md" % (y, w)
        review_due = {"file": fname, "done": fname in reviews}
    weekly = [n for n in reviews if "-W" in n]
    focus = None
    if weekly:
        txt = extract_focus(review_text(ctx.me, weekly[0]))
        if txt:
            focus = {"file": weekly[0], "text": txt}

    pstate = pantry_state(ctx)
    pantry = [dict({k: s.get(k) for k in DASHBOARD_PANTRY_FIELDS}, purchased=s.get("purchased"))
              for s in pstate if s["status"] != "gone"]
    alerts = [p for p in pantry if p["status"] in ("soon", "check", "discard")]

    monday = to - dt.timedelta(days=to.weekday())
    week_days = [monday + dt.timedelta(days=i) for i in range(to.weekday() + 1)]
    week_agg = daily_aggregates(events, week_days)
    training = _dict(settings.get("training"))
    plan = training.get("sessions_per_week")
    plan = plan if is_int(plan) and plan > 0 else DASHBOARD_TRAINING_PLAN
    decisions = settings_decisions(settings, to)

    month_days = [to.replace(day=1) + dt.timedelta(days=i) for i in range(to.day)]
    msum = cost_sum(cdays, month_days)
    spend_month = {"month": to.strftime("%Y-%m"), "from": month_days[0].isoformat(), "to": to.isoformat(),
                   "currency": cs["currency"], "total": _r(sum(v["eur"] for v in msum.values())),
                   "estimated": any(v["est"] for v in msum.values()),
                   "unknown": sum(v["unknown"] for v in msum.values()),
                   "categories": [dict(key=c, eur=v["eur"], est=v["est"], unknown=v["unknown"], any=v["any"])
                                  for c, v in msum.items()]}
    tab_today = {
        "phase": phase_json(phase_now, to) or upcoming_phase_json(phases, to), "next_decision": next_decision(decisions),
        "checklist": checklist, "substances": subs_today,
        "due": {"training": train_due, "training_next": train_next, "measurements": measure_due,
                "review": review_due},
        "pantry_alerts": {"counts": {s: sum(1 for p in pantry if p["status"] == s) for s in ("soon", "check", "discard")},
                          "top": alerts[:3]},
        "week": {"from": monday.isoformat(), "training_n": sum(week_agg[d]["training_n"] for d in week_days),
                 "training_min": sum(week_agg[d]["training_min"] for d in week_days)},
        "training_plan": plan, "focus": focus,
        "spend_month": spend_month,
    }

    # ---------------------------------------------------------------- body
    goals = _dict(settings.get("goals"))
    rate = goals.get("weight_rate_kg_month")
    corridor = None
    if isinstance(rate, list) and len(rate) == 2 and all(is_num(x) for x in rate):
        wlist = sorted((event_day(e), e["kg"]) for e in events if e.get("type") == "weight" and is_num(e.get("kg")))
        anchor_phase = phase_now or (phases[0] if phases else None)
        cands = [w for w in wlist if anchor_phase and w[0] >= anchor_phase["from"]] or wlist
        if cands:
            a_day, a_kg = cands[0]
            lo, hi = min(rate), max(rate)
            corridor = {"anchor_day": a_day.isoformat(), "anchor_kg": a_kg, "rate": [lo, hi],
                        "phase_id": anchor_phase["id"] if anchor_phase and cands[0][0] >= anchor_phase["from"] else None,
                        "days": [{"day": d.isoformat(), "lo": _r(a_kg + lo * (d - a_day).days / 30.4375),
                                  "hi": _r(a_kg + hi * (d - a_day).days / 30.4375)} for d in days_ if d >= a_day]}
    labs = collections.defaultdict(list)
    for e in events:
        if e.get("type") == "lab" and e.get("test"):
            labs[str(e["test"])].append(e)
    lab_rows = []
    for test, evs in sorted(labs.items()):
        evs.sort(key=lambda e: (str(e.get("lab_date") or e["ts"][:10]), e["ts"]))
        cur, prev = evs[-1], evs[-2] if len(evs) > 1 else None
        v, lo, hi = cur.get("value"), cur.get("ref_low"), cur.get("ref_high")
        flag = None
        if is_num(v) and (is_num(lo) or is_num(hi)):
            flag = "low" if is_num(lo) and v < lo else "high" if is_num(hi) and v > hi else "in"
        lab_rows.append({"test": test, "value": v, "unit": cur.get("unit"), "ref_low": lo, "ref_high": hi,
                         "flag": flag, "date": str(cur.get("lab_date") or cur["ts"][:10]),
                         "previous": prev.get("value") if prev else None,
                         "previous_date": str(prev.get("lab_date") or prev["ts"][:10]) if prev else None})
    tab_body = {
        "corridor": corridor, "goals": {"weight_rate_kg_month": rate if corridor else None},
        "circumferences": {m: series(m) for m in CIRCUMFERENCES},
        "bp": series("bp"), "vitals": {m: series(m) for m in VITALS if by_metric.get(m)},
        "labs": lab_rows,
    }

    # ---------------------------------------------------------------- nutrition
    nutrition = _dict(settings.get("nutrition"))
    ntargets = _dict(nutrition.get("targets"))
    protein_t, protein_basis = None, None
    per_kg = goals.get("protein_g_per_kg")
    ref_w = None
    for d in reversed([d for d in all_days if d in weights]):
        ref_w = trend(d)
        break
    if isinstance(per_kg, list) and len(per_kg) == 2 and all(is_num(x) for x in per_kg) and ref_w:
        protein_t = [round(min(per_kg) * ref_w), round(max(per_kg) * ref_w)]
        protein_basis = {"g_per_kg": [min(per_kg), max(per_kg)], "weight_kg": _r(ref_w, 1)}
    else:
        protein_t = _band(ntargets.get("protein_g")) or (
            [ntargets["protein_g_min"], ntargets.get("protein_g_max") if is_num(ntargets.get("protein_g_max")) else None]
            if is_num(ntargets.get("protein_g_min")) else None)
    kcal_t = _band(ntargets.get("kcal")) or (
        [ntargets["kcal_min"], ntargets.get("kcal_max") if is_num(ntargets.get("kcal_max")) else None]
        if is_num(ntargets.get("kcal_min")) else None)
    slots, meal_times, sources = [], [], collections.OrderedDict()
    mac = {"protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    mac_meals, item_protein_n = 0, 0
    for d in days_:
        row = {"day": d.isoformat()}
        for e in sorted(daily[d]["_events"]["meal"], key=lambda e: e["ts"]):
            slot = e.get("slot") if e.get("slot") in MEAL_SLOTS else "other"
            if is_num(e.get("protein_g")):
                row[slot] = row.get(slot, 0) + e["protein_g"]
            t_ = _local_dt(e["ts"])
            meal_times.append({"day": d.isoformat(), "time": t_.strftime("%H:%M"), "minutes": _minutes(t_),
                               "slot": slot, "desc": e.get("desc"), "kcal": e.get("kcal"),
                               "protein_g": e.get("protein_g")})
            if all(is_num(e.get(k)) for k in mac):
                mac_meals += 1
                for k in mac:
                    mac[k] += e[k]
            for it in _list(e.get("items")):
                if isinstance(it, dict) and it.get("name") and is_num(it.get("protein_g")):
                    item_protein_n += 1
                    nm = str(it["name"]).strip()
                    s = sources.setdefault(norm_name(nm) or nm, {"name": nm, "protein_g": 0.0, "n": 0})
                    s["protein_g"] += it["protein_g"]
                    s["n"] += 1
        slots.append(row)
    meal_days = sum(1 for r in day_rows if r["meals"])
    kcal_parts = {"protein_g": mac["protein_g"] * 4, "carbs_g": mac["carbs_g"] * 4, "fat_g": mac["fat_g"] * 9}
    ksum = sum(kcal_parts.values())
    tab_nutrition = {
        "targets": {"protein_g": protein_t, "protein_basis": protein_basis, "kcal": kcal_t},
        "slots": slots, "meal_times": meal_times,
        "macros": {"meals": mac_meals, "days": meal_days,
                   "g_per_day": {k: _r(v / meal_days, 1) if meal_days else None for k, v in mac.items()},
                   "kcal_pct": {k: _r(v / ksum * 100, 1) if ksum else None for k, v in kcal_parts.items()}},
        "protein_sources": sorted(({"name": s["name"], "protein_g": _r(s["protein_g"], 1), "n": s["n"]}
                                   for s in sources.values()), key=lambda s: -s["protein_g"])[:8],
        "items_with_protein": item_protein_n,
    }

    # ---------------------------------------------------------------- kitchen
    purchases = []
    for e in sorted((e for e in pevents if e.get("type") == "purchase"), key=_sort_key_ts):
        d = _day_or_none(e.get("ts"))
        if d is None or d not in wanted:
            continue
        items = [it for it in _list(e.get("items")) if isinstance(it, dict)]
        prices = [it["price_eur"] for it in items if is_num(it.get("price_eur"))]
        purchases.append({"day": d.isoformat(), "store": e.get("store") or None, "items": len(items),
                          "priced_items": len(prices), "total_eur": _r(sum(prices)) if prices else None})
    waste = []
    for s in pstate:
        if not str(s.get("gone_reason") or "").startswith("discarded"):
            continue
        frac = s["remaining"] / s["qty"] if is_num(s.get("remaining")) and is_num(s.get("qty")) and s["qty"] > 0 else 1.0
        frac = max(0.0, min(1.0, frac))
        waste.append({"day": s.get("gone_at"), "name": s.get("name"), "reason": s["gone_reason"].split(":", 1)[-1],
                      "fraction": _r(frac), "eur": _r(s["price_eur"] * frac) if is_num(s.get("price_eur")) else None,
                      "storage": s.get("storage")})
    waste.sort(key=lambda w: w["day"] or "", reverse=True)
    recipes = sorted((e for e in load_events(ctx.cookbook_path) if isinstance(e.get("ts"), str)),
                     key=_sort_key_ts, reverse=True)
    cuisines, skills, ratings = collections.Counter(), [], {"up": 0, "down": 0, "none": 0}
    for e in recipes:
        d = _day_or_none(e["ts"])
        if e.get("status") != "cooked":
            continue
        ratings[e.get("rating") if e.get("rating") in ("up", "down") else "none"] += 1
        if d and (to - d).days < 30 and d <= to:
            cuisines[str(e.get("cuisine") or "?")] += 1
    for e in reversed(recipes):  # oldest first: first time a skill was learned
        if e.get("status") == "cooked" and e.get("skill") and e["skill"] not in [s["skill"] for s in skills]:
            skills.append({"skill": str(e["skill"]), "recipe": e.get("name"), "day": e["ts"][:10]})
    eating_out = []
    for d in days_:
        for e in sorted((e for typ in ("meal", "drink") for e in daily[d]["_events"][typ]), key=lambda e: e["ts"]):
            for cat, eur, _ in event_costs(e, cs):
                if cat == "out" and eur is not None:
                    eating_out.append({"day": d.isoformat(), "time": hhmm(e["ts"]), "type": e.get("type"),
                                       "slot": e.get("slot"), "desc": e.get("desc") or e.get("kind"), "eur": _r(eur)})
    tab_kitchen = {
        "pantry": pantry, "purchases": purchases, "waste": waste, "eating_out": eating_out,
        "currency": cs["currency"],
        "shopping_list": _read_text(ctx.shopping_list_path), "shared": bool(ctx.household),
        "cookbook": [{"day": e["ts"][:10], "name": e.get("name"), "cuisine": e.get("cuisine"),
                      "simplicity": e.get("simplicity"), "nutrition_score": e.get("nutrition_score"),
                      "rating": e.get("rating"), "status": e.get("status"), "skill": e.get("skill")}
                     for e in recipes[:10]],
        "cuisines_30d": dict(sorted(cuisines.items(), key=lambda kv: (-kv[1], kv[0]))),
        "ratings": ratings, "skills": skills,
    }

    # ---------------------------------------------------------------- sleep
    subs = sorted(((_local_dt(e["ts"]), e) for e in events if e.get("type") == "substance"), key=lambda p: p[0])
    nights, sleep_vs, coffee_vs = [], [], []
    alc = {"none": [], "some": []}
    trn = {"rest": [], "training": []}
    for d in days_:
        r = daily[d]
        if r["sleep_h"] is None:
            continue
        anchor = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(20, 0))
        main = None
        for e in r["_events"]["sleep"]:
            try:
                b, w = _local_dt(e["bed"]), _local_dt(e["wake"])
            except (KeyError, ValueError, TypeError):
                continue
            if main is None or (w - b) > (main[1] - main[0]):
                main = (b, w)
        if main:
            nights.append({"day": d.isoformat(), "bed": main[0].strftime("%H:%M"), "wake": main[1].strftime("%H:%M"),
                           "bed_min": int((main[0] - anchor).total_seconds() // 60),
                           "wake_min": int((main[1] - anchor).total_seconds() // 60), "sleep_h": _r(r["sleep_h"])})
        start = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(18, 0))
        end = dt.datetime.combine(d, dt.time(6, 0))
        if main:
            end = min(end, max(main[0], start))
        last = None
        for t_, _ in subs:
            if start <= t_ <= end:
                last = t_
        sleep_vs.append({"day": d.isoformat(), "last_use_prev_evening": last.strftime("%H:%M") if last else None,
                         "minutes_after_18": int((last - start).total_seconds() // 60) if last else None,
                         "sleep_h": _r(r["sleep_h"]), "quality": _r(r["sleep_quality"])})
        prev = d - dt.timedelta(days=1)
        pg = by_day.get(prev, {})
        caf = sorted((e for e in pg.get("drink", []) if is_caffeinated(e)), key=lambda e: e["ts"])
        if caf:
            ct = _local_dt(caf[-1]["ts"])
            coffee_vs.append({"day": d.isoformat(), "last_coffee": ct.strftime("%H:%M"), "minutes": _minutes(ct),
                              "sleep_h": _r(r["sleep_h"])})
        if is_logged(prev):
            units = sum(e.get("alcohol_units") or 0 for e in pg.get("drink", []))
            alc["some" if units > 0 else "none"].append(r["sleep_h"])
            trn["training" if pg.get("training") else "rest"].append(r["sleep_h"])
    bed_mins = [n["bed_min"] for n in nights]
    tab_sleep = {
        "nights": nights,
        "regularity": {"n": len(bed_mins),
                       "bed_sd_min": _r(statistics.pstdev(bed_mins), 0) if len(bed_mins) >= 3 else None,
                       "bed_mean": _hm_of(20 * 60 + statistics.mean(bed_mins)) if bed_mins else None,
                       "wake_mean": _hm_of(20 * 60 + statistics.mean([n["wake_min"] for n in nights])) if nights else None},
        "vs_last_use": sleep_vs, "vs_coffee": coffee_vs,
        "vs_alcohol": {k: _mean_n(v) for k, v in alc.items()},
        "vs_training": {k: _mean_n(v) for k, v in trn.items()},
    }

    # ---------------------------------------------------------------- substances
    trig_all = collections.Counter()
    for e in events:
        if e.get("type") == "substance":
            trig_all[e.get("trigger") or "?"] += e.get("count") or 1
    use_times = collections.Counter()
    for t_, e in subs:
        if t_.date() in wanted:
            use_times[(t_.weekday(), t_.hour)] += e.get("count") or 1
    sub_cfg = _dict(settings.get("substances"))
    base_phase = next((p for p in phases if p["id"] == "baseline"), phases[0] if phases else None)

    def rate_between(a, b):
        ds = [a + dt.timedelta(days=i) for i in range((b - a).days + 1)] if a <= b else []
        ds = [d for d in ds if is_logged(d)]
        return (sum(tobacco_of(d) for d in ds) / len(ds), len(ds)) if ds else (None, 0)

    baseline = None
    if base_phase and base_phase["from"] <= to:
        b_rate, b_n = rate_between(base_phase["from"], min(base_phase["to"] or to, to))
        if b_rate is not None:
            baseline = {"phase_id": base_phase["id"], "name": base_phase["name"],
                        "from": base_phase["from"].isoformat(),
                        "to": min(base_phase["to"] or to, to).isoformat(), "per_day": _r(b_rate), "days": b_n}
    target_now = phase_now["targets"].get("tobacco_per_day") if phase_now else None
    logged_hist = [d for d in all_days if is_logged(d)]
    longest = run = 0
    prev_d = None
    for d in logged_hist:
        if tobacco_of(d) == 0:
            run = run + 1 if prev_d is not None and (d - prev_d).days == 1 and tobacco_of(prev_d) == 0 else 1
            longest = max(longest, run)
        prev_d = d
    current = 0
    d = to
    while is_logged(d) and tobacco_of(d) == 0:
        current += 1
        d -= dt.timedelta(days=1)
    pb_cfg = _dict(sub_cfg.get("plan_b"))
    pb_phase = next((p for p in phases if p["id"] == pb_cfg.get("phase_id")), None)
    plan_b = None
    if pb_cfg and pb_phase and pb_phase["from"] <= to and baseline and baseline["per_day"]:
        window = pb_cfg.get("window_days") if is_int(pb_cfg.get("window_days")) else 14
        thr = pb_cfg.get("threshold_pct_of_baseline") if is_num(pb_cfg.get("threshold_pct_of_baseline")) else 90
        day_n = (to - pb_phase["from"]).days + 1
        last_full = to - dt.timedelta(days=1)
        lo = max(pb_phase["from"], last_full - dt.timedelta(days=6))
        cur_rate, cur_n = rate_between(lo, last_full) if last_full >= pb_phase["from"] else rate_between(to, to)
        pct = cur_rate / baseline["per_day"] * 100 if cur_rate is not None else None
        if pct is None:
            status = None
        elif day_n > window:
            status = "plan_b_due" if pct >= thr else "on_track"
        else:
            status = "watch" if pct >= thr else "on_track"
        plan_b = {"phase_id": pb_phase["id"], "phase_name": pb_phase["name"], "from": pb_phase["from"].isoformat(),
                  "day": day_n, "window_days": window, "threshold_pct": thr, "baseline_per_day": baseline["per_day"],
                  "current_per_day": _r(cur_rate), "current_days": cur_n, "pct_of_baseline": _r(pct, 0),
                  "status": status}
    sub_cats = ("tobacco", "cannabis", "alcohol")
    need = {"tobacco": ("tobacco_eur_per_g", "tobacco_g_per_use"),
            "cannabis": ("cannabis_eur_per_g", "cannabis_g_per_use"), "alcohol": ("alcohol_eur_per_unit",)}
    unknown_cats = {c for d in cdays for c, v in cdays[d].items() if c in sub_cats and v["unknown"]}
    months = collections.OrderedDict()
    for d in sorted(cdays):
        months.setdefault(d.strftime("%Y-%m"), []).append(d)
    cost = {
        "currency": cs["currency"],
        "settings": {k: cs[k] for k in COST_KEYS},
        "missing": sorted({k for c in unknown_cats for k in need[c] if cs[k] is None}),
        "categories": [c for c in sub_cats if any(c in cdays[d] for d in cdays)],
        "per_month": [dict(month=m, **cost_sum(cdays, ds, sub_cats)) for m, ds in months.items()
                      if any(c in cdays[d] for d in ds for c in sub_cats)],
        "days": [dict(day=d.isoformat(), **{c: _r(cdays.get(d, {}).get(c, {}).get("eur", 0.0)) for c in sub_cats})
                 for d in days_],
    }
    use_price = (cs["tobacco_g_per_use"] * cs["tobacco_eur_per_g"]
                 if cs["tobacco_g_per_use"] is not None and cs["tobacco_eur_per_g"] is not None else None)
    cost["tobacco_eur_per_use"] = _r(use_price, 3)
    step = pb_phase or next((p for p in phases if base_phase and p["from"] > base_phase["from"]), None)
    if use_price is not None and baseline and step and step["from"] <= to:
        s_rate, s_n = rate_between(step["from"], to)
        if s_rate is not None:
            cost["saved"] = {"since": step["from"].isoformat(), "phase_name": step["name"], "days": s_n,
                             "per_day": _r(s_rate), "baseline_per_day": baseline["per_day"],
                             "eur": _r((baseline["per_day"] - s_rate) * s_n * use_price)}
    tab_substances = {
        "active": "substances" in modules or bool(trig_all),
        "substance_kinds": dict(kinds.most_common()), "triggers_total": dict(trig_period.most_common()),
        "trigger_order": [k for k, _ in sorted(trig_all.items(), key=lambda kv: (-kv[1], kv[0]))],
        "use_times": [{"weekday": wd, "hour": h, "count": c} for (wd, h), c in sorted(use_times.items())],
        "baseline": baseline, "target_per_day": target_now if is_num(target_now) else None,
        "streaks": {"free_days": sum(1 for r in day_rows if r["logged"] and r["tobacco_n"] == 0),
                    "logged_days": sum(1 for r in day_rows if r["logged"]), "current": current, "longest": longest},
        "plan_b": plan_b, "cost": cost,
    }

    # ---------------------------------------------------------------- training
    lift_days = collections.defaultdict(dict)  # ex -> day -> best
    lift_all = collections.Counter()
    last_top = {}
    vol = collections.Counter()
    for e in sorted((e for e in events if e.get("type") == "training"), key=_sort_key_ts):
        d = event_day(e)
        for s in _list(e.get("sets")):
            if not isinstance(s, dict) or not s.get("ex") or not is_num(s.get("kg")):
                continue
            ex = str(s["ex"])
            lift_all[ex] += 1
            reps = [x for x in _list(s.get("reps")) if is_int(x) and x > 0]
            top_reps = max(reps) if reps else None
            prev_top = last_top.get(norm_name(ex))
            if not prev_top or prev_top["day"] != d.isoformat() or s["kg"] > prev_top["kg"]:
                last_top[norm_name(ex)] = {"day": d.isoformat(), "kg": s["kg"], "reps": top_reps}
            if d not in wanted:
                continue
            vol[d] += s["kg"] * sum(reps)
            e1 = _epley(s["kg"], top_reps)
            cur = lift_days[ex].get(d)
            if cur is None or (s["kg"], top_reps or 0) > (cur["top_kg"], cur["top_reps"] or 0):
                cur = {"day": d.isoformat(), "top_kg": s["kg"], "top_reps": top_reps,
                       "e1rm": cur["e1rm"] if cur else None}
            if e1 is not None and (cur["e1rm"] is None or e1 > cur["e1rm"]):
                cur["e1rm"] = e1
            lift_days[ex][d] = cur
    by_days = sorted(lift_days, key=lambda x: (-len(lift_days[x]), -lift_all[x], x))
    main = sorted(by_days[:4], key=lambda x: (-lift_all[x], x))
    cal_from = max(frm, to - dt.timedelta(days=83))
    cal_from = min(cal_from, to - dt.timedelta(days=27))
    sessions, endurance = [], []
    for d in all_days:
        for e in sorted(by_day[d]["training"], key=_sort_key_ts):
            cat = training_category(e.get("kind"))
            if cal_from <= d <= to:
                sessions.append({"day": d.isoformat(), "kind": e.get("kind"), "category": cat, "plan": e.get("plan"),
                                 "dur_min": e.get("dur_min")})
            if d in wanted and cat == "endurance":
                km, mins = e.get("distance_km"), e.get("dur_min")
                endurance.append({"day": d.isoformat(), "kind": e.get("kind"), "dur_min": mins, "distance_km": km,
                                  "avg_hr": e.get("avg_hr"),
                                  "pace_min_km": _r(mins / km) if is_num(km) and km > 0 and is_num(mins) and mins > 0 else None})
    plan_doc = None
    try:
        raw = _read_text(os.path.join(ctx.me, "plans", "training.json")) if ctx.consent else None
        plan_doc = json.loads(raw) if raw else None
    except ValueError:
        plan_doc = None
    next_goals = []
    for x in _list(_dict(plan_doc).get("exercises")):
        if not _dict(x).get("name"):
            continue
        lt = last_top.get(norm_name(x["name"]))
        next_goals.append({"name": str(x["name"]), "plan": x.get("plan"), "sets": x.get("sets"), "reps": x.get("reps"),
                           "kg": x.get("kg"), "next_kg": x.get("next_kg"),
                           "last_day": lt["day"] if lt else None, "last_kg": lt["kg"] if lt else None,
                           "last_reps": lt["reps"] if lt else None})
    tab_training = {
        "plan": plan, "schedule": {str(k): str(v) for k, v in _dict(training.get("schedule")).items()},
        "calendar": {"from": cal_from.isoformat(), "to": to.isoformat(), "sessions": sessions},
        "lifts": {"exercises": {ex: [dict(v, e1rm=_r(v["e1rm"], 1)) for _, v in sorted(lift_days[ex].items())]
                                for ex in main}, "others": sorted(by_days[4:])},
        "volume": [{"day": d.isoformat(), "kg": _r(vol[d], 1)} for d in days_ if vol.get(d)],
        "endurance": endurance,
        "tests": {m: by_metric[m] for m in sorted(by_metric) if m.startswith("test_")},
        "next_goals": next_goals,
    }

    # ---------------------------------------------------------------- journal
    timeline = []
    for d in reversed(days_):
        for e in sorted((e for typ in LOG_TYPES for e in daily[d]["_events"][typ]), key=lambda e: e["ts"], reverse=True):
            text = e.get("text") if e.get("type") == "note" else e.get("desc") if e.get("type") == "symptom" else None
            base = {"day": d.isoformat(), "time": hhmm(e["ts"]), "type": e.get("type")}
            if text:
                timeline.append(dict(base, text=str(text), tags=_list(e.get("tags")), severity=e.get("severity")))
            if e.get("note"):
                timeline.append(dict(base, text=str(e["note"]), tags=[], severity=None, field="note"))
    rev_list = []
    for n in reviews:
        rev_list.append({"file": n, "kind": "weekly" if "-W" in n else "monthly",
                         "title": review_title(review_text(ctx.me, n), n)})
    tab_journal = {"reviews": rev_list, "timeline": timeline, "decisions": decisions}

    return {
        "schema": 2, "today": to.isoformat(), "generated_at": ctx.now().isoformat(timespec="seconds"),
        "period": {"key": key, "from": frm.isoformat(), "to": to.isoformat(), "days": len(days_),
                   "days_logged": sum(1 for r in day_rows if r["logged"])},
        "language": settings.get("language") or "en", "modules": modules,
        "profile": ctx.profile_json(),
        "household": ({"name": ctx.household.get("name"),
                       "members": [{k: m[k] for k in ("id", "name", "color", "consent", "initials")}
                                   for m in ctx.members()]} if ctx.household else None),
        "days": day_rows, "previous": previous,
        "tabs": {"today": tab_today, "body": tab_body, "nutrition": tab_nutrition, "kitchen": tab_kitchen,
                 "sleep": tab_sleep, "substances": tab_substances, "training": tab_training, "journal": tab_journal},
    }


def bp_category(sys_, dia):
    """ESH 2023 office categories (the higher of systolic/diastolic wins)."""
    if sys_ >= 140 or dia >= 90:
        return "hypertension"
    if sys_ >= 130 or dia >= 85:
        return "high_normal"
    if sys_ >= 120 or dia >= 80:
        return "normal"
    return "optimal"


KEY_COOKIE = "bos_key"
KEY_COOKIE_MAX_AGE = 400 * 86400
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]")
LOCAL_ONLY_PATHS = ("/devices", "/devices.html", "/api/devices")
UNAUTHORIZED_HTML = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark">
<title>body-os</title><style>body{font:16px/1.5 -apple-system,system-ui,sans-serif;max-width:30em;margin:12vh auto;
padding:0 20px;color:#52514e}h1{font-size:20px;color:inherit}@media(prefers-color-scheme:dark){body{background:#111110;
color:#c3c2b7}}</style></head><body><h1>body-os &middot; kein Zugriff</h1>
<p>Diesen Link vom Mac aus &ouml;ffnen / QR-Code scannen: auf dem Mac <b>http://127.0.0.1:PORT/devices</b> aufrufen
und den QR-Code mit diesem Ger&auml;t scannen.</p>
<p lang="en">No access. Open the device link from the Mac, or scan the QR code shown at
<b>http://127.0.0.1:PORT/devices</b> on the Mac.</p></body></html>"""


def server_json_path(ctx):
    """Household key file: household/server.json, or <data>/server.json in single-user mode."""
    return os.path.join(ctx.household_dir, "server.json") if ctx.household else os.path.join(ctx.data, "server.json")


def load_server_config(path):
    cfg = read_json_file(path, {})
    return cfg if isinstance(cfg, dict) else {}


def _valid_key(k):
    return isinstance(k, str) and len(k) >= 32 and re.match(r"^[A-Za-z0-9_-]+$", k) is not None


def ensure_server_key(path, rotate=False):
    """Return the household key, creating (or with rotate=True replacing) it. File mode 0600."""
    cfg = load_server_config(path)
    if rotate or not _valid_key(cfg.get("key")):
        cfg["schema"] = 1
        cfg["key"] = secrets.token_urlsafe(32)
        cfg["created"] = dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
        cfg.setdefault("allowed_hosts", [])
        write_json_file(path, cfg, mode=0o600)
    return cfg["key"]


def is_loopback_ip(ip):
    try:
        a = ipaddress.ip_address(str(ip).split("%")[0])
    except ValueError:
        return False
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return a.is_loopback


def local_hostnames():
    """mDNS names of this machine, primary first: <LocalHostName>.local (macOS scutil), hostname."""
    lhn = None
    if sys.platform == "darwin":
        try:
            r = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=3)
            lhn = r.stdout.strip() if r.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            lhn = None
    hn = socket.gethostname().strip().lower()
    short = hn.split(".")[0]
    out = []
    for n in ((lhn or short).lower() + ".local", hn, short + ".local"):
        if n and n not in out:
            out.append(n)
    return out


def lan_ipv4s():
    """All non-loopback IPv4 addresses of this machine, home-network ranges first.

    The default-route address alone is not enough: with a VPN up it is the tunnel address, while
    phones in the home Wi-Fi reach the Mac via its Wi-Fi/Ethernet address.
    """
    found = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1: only selects the outgoing interface, sends nothing
            found.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        out = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=3).stdout
        found += re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)", out)
    except (OSError, subprocess.SubprocessError):
        pass
    ips = []
    for ip in found:
        if ip and not ip.startswith(("127.", "169.254.")) and ip != "0.0.0.0" and ip not in ips:
            ips.append(ip)
    rank = lambda ip: 0 if ip.startswith("192.168.") else 1 if re.match(r"172\.(1[6-9]|2\d|3[01])\.", ip) else 2
    return sorted(ips, key=rank)


def device_links(key, port):
    hosts = local_hostnames()[:1] + lan_ipv4s()
    return [{"host": h, "url": "http://%s:%d/" % (h, port), "link": "http://%s:%d/?key=%s" % (h, port, key)}
            for h in hosts]


def make_dashboard_server(ctx, port=8030, default_days="30", today=None, host="127.0.0.1", is_local=None):
    """Read-only HTTP server for tools/dashboard/ and its JSON API.

    GET /api/profiles, /api/data?profile=ID&days=N, /api/review?profile=ID&file=YYYY-Www.md|YYYY-MM.md.
    Data is rebuilt from the instance/household folders on every request.

    Access: loopback clients need no key. Any other client needs the household key (server.json),
    as cookie bos_key or once via GET /?key=... (sets the cookie, redirects to /). /devices (QR code
    and device link) is loopback-only. Requests whose Host header is not a name of this machine are
    refused (DNS-rebinding guard). `is_local(ip)` decides what counts as loopback (injectable for
    tests; also settable as srv.is_local). Port 0 picks a free port (tests)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, unquote, urlsplit

    root = os.path.realpath(DASHBOARD_DIR)
    key_path = server_json_path(ctx)
    lan_names = {"names": [], "at": 0.0}  # scutil + UDP probe; refreshed on a miss after 30 s (DHCP changes)

    def fresh(profile=None):
        return ctx.for_profile(profile) if profile else ctx.for_profile(None)

    def server_cfg():
        return load_server_config(key_path)

    class Handler(BaseHTTPRequestHandler):
        def version_string(self):
            return "body-os"

        def log_message(self, fmt, *a):  # quiet; errors are visible in the browser
            pass

        def _send(self, code, body, ctype, cache="no-store", headers=()):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", DASHBOARD_CSP)
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

        def _redirect(self, cookie_key=None):
            headers = [("Location", "/")]
            if cookie_key:
                headers.append(("Set-Cookie", "%s=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d"
                                % (KEY_COOKIE, cookie_key, KEY_COOKIE_MAX_AGE)))
            self._send(302, b"", "text/plain; charset=utf-8", headers=headers)

        def _unauthorized(self):
            self._send(401, UNAUTHORIZED_HTML.replace("PORT", str(self.server.server_address[1])),
                       "text/html; charset=utf-8")

        def _host_ok(self):
            hostport = (self.headers.get("Host") or "").strip().lower()
            m = re.match(r"^(\[[0-9a-f:.]+\]|[^:\[\]/]+)(?::(\d+))?$", hostport)
            if not m:
                return False
            name, p = m.group(1), m.group(2) or "80"
            if p != str(self.server.server_address[1]):
                return False
            if name in LOOPBACK_HOSTS:
                return True
            extra = [str(h).lower() for h in server_cfg().get("allowed_hosts") or [] if isinstance(h, str)]
            if name in extra:
                return True
            if name in lan_names["names"]:
                return True
            import time
            if time.monotonic() - lan_names["at"] > 30 or not lan_names["at"]:
                lan_names["names"], lan_names["at"] = local_hostnames() + lan_ipv4s(), time.monotonic()
            return name in lan_names["names"]

        def _cookie_key(self):
            # by hand: one malformed foreign cookie (cookies are not port-isolated) must not hide ours
            for part in ";".join(self.headers.get_all("Cookie") or []).split(";"):
                name, sep, value = part.strip().partition("=")
                if sep and name.strip() == KEY_COOKIE:
                    return value.strip().strip('"')
            return None

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, "forbidden host", "text/plain; charset=utf-8")
            parts = urlsplit(self.path)
            qs = parse_qs(parts.query)
            local = bool(self.server.is_local(self.client_address[0]))
            key = server_cfg().get("key")
            key = key if _valid_key(key) else None
            if parts.path == "/" and "key" in qs:  # one-time device link: set cookie, strip the key
                given = qs["key"][0]
                if key and hmac.compare_digest(given.encode("utf-8"), key.encode("utf-8")):
                    return self._redirect(key)
                return self._redirect() if local else self._unauthorized()
            if not local:
                given = self._cookie_key()
                if not (key and given and hmac.compare_digest(given.encode("utf-8"), key.encode("utf-8"))):
                    return self._unauthorized()
                norm = "/" + "/".join(x for x in unquote(parts.path).lower().split("/") if x)
                if norm in LOCAL_ONLY_PATHS:
                    return self._send(403, "only on this computer", "text/plain; charset=utf-8")
            if parts.path == "/api/profiles":
                c = fresh()
                return self._json(200, {"household": ({"name": c.household.get("name")} if c.household else None),
                                        "members": [{k: m[k] for k in ("id", "name", "color", "consent", "initials")}
                                                    for m in c.members()],
                                        "default": c.profile_id, "language": c.settings.get("language") or "en"})
            if parts.path in ("/api/data", "/api/review"):
                profile = qs.get("profile", [None])[0]
                try:
                    base = fresh()
                    if profile is not None and profile not in [m["id"] for m in base.members()]:
                        return self._json(404, {"error": "unknown profile"})
                    c = fresh(profile)
                except BosError as e:
                    return self._json(500, {"error": str(e)})
                if parts.path == "/api/data":
                    days = qs.get("days", [default_days])[0]
                    if days not in DASHBOARD_PERIODS:
                        return self._json(400, {"error": "days must be one of %s" % "/".join(DASHBOARD_PERIODS)})
                    try:
                        return self._json(200, dashboard_data(c, days))
                    except Exception as e:  # report, never crash the server
                        return self._json(500, {"error": "%s: %s" % (type(e).__name__, e)})
                name = qs.get("file", [""])[0]
                if not REVIEW_FILE_RE.match(name):
                    return self._json(400, {"error": "file must look like YYYY-Www.md or YYYY-MM.md"})
                text = review_text(c.me, name) if c.consent else None
                if text is None:
                    return self._json(404, {"error": "no such review"})
                return self._json(200, {"file": name, "text": text})
            if parts.path == "/api/devices":
                port_ = self.server.server_address[1]
                lan = self.server.server_address[0] not in ("127.0.0.1", "::1", "localhost")
                return self._json(200, {"lan": lan, "port": port_, "key_set": bool(key),
                                        "links": device_links(key, port_) if key else []})
            if parts.path == "/manifest.webmanifest":
                man = read_json_file(os.path.join(root, "manifest.webmanifest"), {})
                if not local and key:  # home-screen apps may not share Safari's cookies: carry the key
                    man["start_url"] = "/?key=" + key
                return self._send(200, json.dumps(man, ensure_ascii=False), DASHBOARD_TYPES[".webmanifest"])
            path = unquote(parts.path)
            if path in ("/devices", "/devices/"):
                path = "/devices.html"
            segs = [s for s in path.split("/") if s]
            if ("\\" in path or "\x00" in path or any(s.startswith(".") for s in segs)):
                return self._send(404, "not found", "text/plain; charset=utf-8")
            full = os.path.realpath(os.path.join(root, *(segs or ["index.html"])))
            ctype = DASHBOARD_TYPES.get(os.path.splitext(full)[1].lower())
            if not full.startswith(root + os.sep) or not os.path.isfile(full) or not ctype:
                return self._send(404, "not found", "text/plain; charset=utf-8")
            with open(full, "rb") as f:
                self._send(200, f.read(), ctype, cache="no-cache")

        do_HEAD = do_GET

    srv = ThreadingHTTPServer((host, port), Handler)
    srv.is_local = is_local or is_loopback_ip
    return srv


def cmd_dashboard(ctx, args):
    if not os.path.isdir(ctx.me):
        print("note: no instance folder at %s yet - the dashboard will be empty" % ctx.me, file=sys.stderr)
    kpath = server_json_path(ctx)
    if args.rotate_key:
        ensure_server_key(kpath, rotate=True)
        print("household key rotated (%s) - every phone/tablet must open the new device link once" % kpath)
        if not args.lan:
            print("start `bos.py dashboard --lan` (or restart the service) and open /devices on this computer")
            return 0
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    key = ensure_server_key(kpath) if args.lan else None
    try:
        srv = make_dashboard_server(ctx, args.port, args.days, today=args.today, host=host)
    except OSError as e:
        raise BosError("cannot listen on %s:%d (%s)" % (host, args.port, e))
    port = srv.server_address[1]
    print("dashboard: http://127.0.0.1:%d/  (read-only, Ctrl+C to stop)" % port, flush=True)
    if args.lan:
        links = device_links(key, port)
        print("LAN:       " + "   ".join(l["url"] for l in links))
        if links and sys.stdout.isatty():  # never write the key into a log file (service mode)
            print("device link (open once per phone/tablet; keep it private - it grants access to all profiles):")
            print("           " + links[0]["link"])
        print("QR code:   open http://127.0.0.1:%d/devices on this computer" % port)
        print("note: macOS may ask whether Python may accept incoming network connections - allow it.", flush=True)
    else:
        print("           localhost only; add --lan to reach it from phones in your home network", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


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


def init_instance(dest, overrides=None):
    """Copy missing templates/me files into dest and create the standard folders. If settings.json
    is created here, `overrides` are applied to it. Returns the number of copied files."""
    tpl = os.path.join(ROOT, "templates", "me")
    os.makedirs(dest, exist_ok=True)
    copied, new_settings = 0, False
    if os.path.isdir(tpl):
        for base, _, files in os.walk(tpl):
            dst_dir = os.path.join(dest, os.path.relpath(base, tpl))
            os.makedirs(dst_dir, exist_ok=True)
            for f in files:
                dst = os.path.join(dst_dir, f)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(base, f), dst)
                    copied += 1
                    new_settings = new_settings or os.path.realpath(dst) == os.path.realpath(
                        os.path.join(dest, "settings.json"))
    for sub in ("log", "pantry", "recipes", "plans", "reviews", "doctor", "inbox"):
        os.makedirs(os.path.join(dest, sub), exist_ok=True)
    if new_settings and overrides:
        sp = os.path.join(dest, "settings.json")
        st = read_json_file(sp, {})
        st.update(overrides)
        write_json_file(sp, st)
    return copied


def git_init_private(path, label):
    if is_own_repo(path):
        print("%s is already a git repository" % label)
        return
    r = git(["init", "-q"], path)
    print("git init in %s: %s" % (label, "ok (no remote - keep it that way)" if r.returncode == 0 else r.stderr.strip()))


def cmd_init(ctx, args):
    copied = init_instance(ctx.me)
    print("copied %d template file(s) into %s" % (copied, ctx.me))
    git_init_private(ctx.me, os.path.relpath(ctx.me, ctx.base) + "/")
    r = git(["config", "core.hooksPath", ".githooks"], ctx.root)
    print("engine hooks: %s" % ("core.hooksPath=.githooks" if r.returncode == 0 else r.stderr.strip()))
    return 0


# --------------------------------------------------------------------------------------------
# household / profile
# --------------------------------------------------------------------------------------------

def _free_color(members):
    used = {m.get("color") for m in members}
    return next((c for c in MEMBER_COLORS if c not in used), MEMBER_COLORS[len(members) % len(MEMBER_COLORS)])


def _check_new_member(hh, pid, name, color):
    if not PROFILE_ID_RE.match(pid or ""):
        raise BosError("member id must be lowercase letters/digits/-/_ (max 32), e.g. 'alex'")
    if any(m["id"] == pid for m in hh["members"]):
        raise BosError("member %r already exists" % pid)
    if not (name or "").strip():
        raise BosError("--name is required")
    if color and color not in MEMBER_COLORS:
        raise BosError("--color must be one of %s" % "/".join(MEMBER_COLORS))


def _write_household(hdir, hh):
    errs = household_errors(hh)
    if errs:
        raise BosError("household.json would be invalid: " + "; ".join(errs))
    write_json_file(os.path.join(hdir, "household.json"), hh)


def cmd_household_init(ctx, args):
    hdir = ctx.household_dir or DEFAULT_HOUSEHOLD
    base = os.path.dirname(hdir)
    hpath = os.path.join(hdir, "household.json")
    if os.path.exists(hpath):
        hh = read_json_file(hpath)
        if household_errors(hh):
            raise BosError("existing %s is invalid: %s" % (hpath, "; ".join(household_errors(hh))))
        print("household.json exists - adding what is missing")
    else:
        hh = {"schema": 1, "name": None, "members": [], "default_member": None}
    if args.name:
        hh["name"] = args.name
    me_dir = os.path.abspath(ctx.opts["me"]) if ctx.opts.get("me") else os.path.join(base, "me")
    me_rel = os.path.relpath(me_dir, base).replace(os.sep, "/")
    registered = next((m for m in hh["members"] if _same_path(os.path.join(base, m["path"]), me_dir)), None)
    has_me = os.path.isdir(me_dir) and bool(os.listdir(me_dir))
    if has_me and not registered:
        if not (args.member_id and args.member_name):
            raise BosError("%s/ exists - register it as a member: --member-id ID --member-name NAME [--color C]"
                           % me_rel)
        if me_rel.startswith("..") or not member_path_ok(me_rel):
            raise BosError("instance %s must be a folder inside %s" % (me_dir, base))
        _check_new_member(hh, args.member_id, args.member_name, args.color)
        registered = {"id": args.member_id, "name": args.member_name.strip(),
                      "color": args.color or _free_color(hh["members"]), "path": me_rel, "consent": True}
        hh["members"].append(registered)
        print("registered %s/ as member %r (%s, consent: yes)" % (me_rel, registered["id"], registered["color"]))
    if registered and not hh.get("default_member"):
        hh["default_member"] = registered["id"]
    os.makedirs(hdir, exist_ok=True)
    _write_household(hdir, hh)
    print("wrote %s" % os.path.relpath(hpath, base))
    spath = os.path.join(hdir, "settings.json")
    if not os.path.exists(spath):
        mine = read_json_file(os.path.join(me_dir, "settings.json"), {}) if has_me else {}
        mine = mine if isinstance(mine, dict) else {}
        shared = {"schema": 1}
        for k in ("language", "timezone") + SHARED_SETTINGS:
            if k in mine:
                shared[k] = mine[k]
        if isinstance(mine.get("costs"), dict) and mine["costs"].get("currency"):
            shared["costs"] = {"currency": mine["costs"]["currency"]}
        write_json_file(spath, shared)
        print("wrote %s (shared: %s)" % (os.path.relpath(spath, base), ", ".join(k for k in shared if k != "schema")))
    for sub in ("pantry", "recipes"):
        os.makedirs(os.path.join(hdir, sub), exist_ok=True)
    moved = kept = 0
    if has_me:
        for sub in ("pantry", "recipes"):
            for b, _, files in os.walk(os.path.join(me_dir, sub)):
                for f in sorted(files):
                    src = os.path.join(b, f)
                    rel = os.path.relpath(src, me_dir)
                    dst = os.path.join(hdir, rel)
                    if os.path.exists(dst) and os.path.getsize(dst) > 0:
                        kept += 1
                        print("kept  %s/%s - household/%s already has content; merge by hand "
                              "(bos doctor warns until one is gone)" % (me_rel, rel, rel))
                        continue
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(src, dst)
                    moved += 1
                    print("moved %s/%s -> household/%s" % (me_rel, rel, rel))
    git_init_private(hdir, "household/")
    print("%d file(s) moved, %d kept. Commit both private repos, e.g.:\n"
          "  git -C %s add -A && git -C %s commit -qm 'kitchen moved to household'\n"
          "  git -C household add -A && git -C household commit -qm 'household init'"
          % (moved, kept, me_rel, me_rel))
    return 0


def cmd_profile_add(ctx, args):
    if not ctx.household:
        raise BosError("no household yet - run `bos.py household init` first")
    hh = read_json_file(os.path.join(ctx.household_dir, "household.json"))
    _check_new_member(hh, args.id, args.name, args.color)
    rel = (args.path or "people/" + args.id).strip("/")
    if not member_path_ok(rel):
        raise BosError("--path must be a relative folder like people/%s" % args.id)
    if any(m["path"].strip("/") == rel for m in hh["members"]):
        raise BosError("%s already belongs to another member" % rel)
    dest = os.path.join(ctx.base, *rel.split("/"))
    if os.path.isdir(dest) and os.listdir(dest) and not os.path.exists(os.path.join(dest, "settings.json")):
        raise BosError("%s exists and is not an instance folder" % dest)
    lang = args.language or ctx.household_settings.get("language") or ctx.settings.get("language") or "en"
    copied = init_instance(dest, {"language": lang, "modules": []})
    print("created %s/ (%d template file(s), language %s, modules [] until onboarding)" % (rel, copied, lang))
    git_init_private(dest, rel + "/")
    m = {"id": args.id, "name": args.name.strip(), "color": args.color or _free_color(hh["members"]),
         "path": rel, "consent": bool(args.consent)}
    hh["members"].append(m)
    _write_household(ctx.household_dir, hh)
    print("registered member %r (%s, consent: %s)" % (m["id"], m["color"], "yes" if m["consent"] else "no"))
    if not m["consent"]:
        print("nothing is logged for %s until their own interview is done and they agree: "
              "`bos.py profile consent %s`" % (m["name"], m["id"]))
    return 0


def cmd_profile_list(ctx, args):
    members = ctx.members()
    if args.json:
        print(dumps({"household": ctx.household.get("name") if ctx.household else None,
                     "default": ctx.profile_id, "members": members}))
        return 0
    if not ctx.household:
        rel = os.path.relpath(ctx.me, ctx.base)
        print("single-user mode (no household/household.json): profile 'me' -> %s"
              % (ctx.me if rel.startswith("..") else rel))
        return 0
    default = ctx.household.get("default_member")
    for m in members:
        print("%s %-12s %-16s %-8s consent:%-3s %s" % ("*" if m["id"] == default else " ", m["id"], m["name"],
                                                      m["color"], "yes" if m["consent"] else "no", m["path"]))
    return 0


def cmd_profile_consent(ctx, args):
    if not ctx.household:
        raise BosError("no household - consent applies to household members only")
    hh = read_json_file(os.path.join(ctx.household_dir, "household.json"))
    m = next((m for m in hh["members"] if m["id"] == args.id), None)
    if m is None:
        raise BosError("unknown profile %r" % args.id)
    m["consent"] = not args.revoke
    _write_household(ctx.household_dir, hh)
    print("%s: consent %s" % (m["id"], "granted - logging enabled" if m["consent"] else "revoked - nothing new is logged"))
    return 0


# --------------------------------------------------------------------------------------------
# sync (home server as source of truth for the private repos)
# --------------------------------------------------------------------------------------------

SYNC_REMOTE = "home"
UNION_ATTR = "*.jsonl merge=union\n"


def private_repos(ctx):
    """[(label, path)] of every private repo: household/ and each member folder, or just me/."""
    if ctx.household:
        out = [("household", ctx.household_dir)]
        for m in ctx.household["members"]:
            out.append((m["id"], ctx.for_profile(m["id"]).me))
        return out
    return [("me", ctx.me)]


def remote_host(url):
    """Host part of a git remote URL; '' for local paths."""
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]*@)?(\[[^\]]+\]|[^:/]+)", url, re.I)
    if m:
        return m.group(1).strip("[]").lower()
    m = re.match(r"^(?:[^@/:]+@)?([^:/]+):(?!//)", url)  # scp-like user@host:path
    if m and not os.path.exists(url):
        return m.group(1).lower()
    return ""


def is_home_remote(url, allowed=()):
    """True for local paths, *.local / *.fritz.box / *.home.arpa names, private or link-local IPs,
    and hosts listed in settings sync.allowed_hosts. Anything else (GitHub, cloud) is not home."""
    host = remote_host(url)
    if not host:
        return True
    if host in {h.lower() for h in allowed} or host == "localhost":
        return True
    if host.endswith((".local", ".fritz.box", ".home.arpa", ".lan")):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_link_local or ip.is_loopback
    except ValueError:
        return False


def sync_allowed_hosts(ctx):
    hosts = []
    for path in ([os.path.join(ctx.household_dir, "settings.json")] if ctx.household else []) + \
            [os.path.join(ctx.me, "settings.json")]:
        cfg = _dict(read_json_file(path, {}))
        hosts += [h for h in _list(_dict(cfg.get("sync")).get("allowed_hosts")) if isinstance(h, str)]
    return hosts


def _ensure_union_merge(path):
    """Concurrent appends to the same JSONL file from two devices merge as a union instead of conflicting."""
    ga = os.path.join(path, ".gitattributes")
    cur = open(ga, encoding="utf-8").read() if os.path.exists(ga) else ""
    if UNION_ATTR.strip() not in cur:
        with open(ga, "a", encoding="utf-8") as f:
            f.write(("" if not cur or cur.endswith("\n") else "\n") + UNION_ATTR)
        return True
    return False


def _git_ok(args, cwd, quiet=False):
    r = git(args, cwd)
    if r.returncode != 0 and not quiet:
        print("  git %s: %s" % (" ".join(args), (r.stderr or r.stdout).strip().replace("\n", "\n  ")))
    return r


def cmd_sync_setup(ctx, args):
    """Create the private repos on the home server (inside its engine clone) and add them as `home` remotes."""
    target, base = args.host, args.path.rstrip("/")
    if not is_home_remote("%s:%s" % (target, base), sync_allowed_hosts(ctx) + [target.split("@")[-1]]) \
            and not args.force:
        raise BosError("%s does not look like a home-network host (.local, private IP). Use --force only if "
                       "you are sure it is your own device." % target)
    ssh = ["ssh", "-o", "BatchMode=yes", target]
    engine = "https://github.com/fabianxvogt/body-os.git" if not args.engine_url else args.engine_url
    script = ("set -e; if [ ! -d %(b)s/.git ]; then git clone -q %(e)s %(b)s; fi; cd %(b)s && git config core.hooksPath .githooks"
              % {"b": base, "e": engine})
    print("$ ssh %s '<clone engine into %s if missing>'" % (target, base))
    if not args.dry_run and subprocess.run(ssh + [script]).returncode != 0:
        raise BosError("could not prepare the engine clone on %s" % target)
    for label, path in private_repos(ctx):
        if not is_own_repo(path):
            print("skip %s: %s is not a git repo" % (label, path))
            continue
        rel = os.path.relpath(path, ctx.base)
        if rel.startswith(".."):
            raise BosError("%s lies outside %s; cannot mirror its layout" % (path, ctx.base))
        remote_dir = "%s/%s" % (base, rel)
        url = "%s:%s" % (target, remote_dir)
        print("%s -> %s" % (label, url))
        if args.dry_run:
            continue
        if _ensure_union_merge(path):
            git(["add", ".gitattributes"], path)
            git(["commit", "-qm", "sync: union merge for jsonl"], path)
        init = ("set -e; mkdir -p %(d)s; cd %(d)s; [ -d .git ] || git init -q -b main; "
                "git config receive.denyCurrentBranch updateInstead" % {"d": remote_dir})
        if subprocess.run(ssh + [init]).returncode != 0:
            raise BosError("could not create %s on %s" % (remote_dir, target))
        existing = git(["remote", "get-url", SYNC_REMOTE], path)
        git(["remote", "set-url" if existing.returncode == 0 else "add", SYNC_REMOTE, url], path)
        if _git_ok(["push", "-q", "-u", SYNC_REMOTE, "HEAD:main"], path).returncode != 0:
            raise BosError("push of %s failed" % label)
    print("done. The home server is now the source of truth; run `bos.py sync` before and after check-ins.")
    return 0


def cmd_sync(ctx, args):
    """Pull, then push every private repo that has a `home` remote. Commits pending changes first."""
    allowed, failures, synced = sync_allowed_hosts(ctx), 0, 0
    for label, path in private_repos(ctx):
        if not is_own_repo(path):
            continue
        url = git(["remote", "get-url", SYNC_REMOTE], path)
        if url.returncode != 0:
            print("%-10s no '%s' remote (local only)" % (label, SYNC_REMOTE))
            continue
        url = url.stdout.strip()
        if not is_home_remote(url, allowed):
            print("%-10s REFUSED: remote %s is not on the home network" % (label, url))
            failures += 1
            continue
        if _ensure_union_merge(path):
            git(["add", ".gitattributes"], path)
        if git(["status", "--porcelain"], path).stdout.strip():
            git(["add", "-A"], path)
            git(["commit", "-qm", "sync %s" % ctx.now().strftime("%Y-%m-%d %H:%M")], path)
        if not args.push_only:
            fetched = _git_ok(["fetch", "-q", SYNC_REMOTE], path)
            if fetched.returncode != 0:
                failures += 1
                continue
            if git(["rev-parse", "-q", "--verify", "%s/main" % SYNC_REMOTE], path).returncode == 0:
                if _git_ok(["merge", "-q", "--no-edit", "%s/main" % SYNC_REMOTE], path).returncode != 0:
                    print("%-10s MERGE CONFLICT - resolve in %s, commit, then sync again" % (label, path))
                    failures += 1
                    continue
        if not args.pull_only and _git_ok(["push", "-q", SYNC_REMOTE, "HEAD:main"], path).returncode != 0:
            failures += 1
            continue
        synced += 1
        print("%-10s synced with %s" % (label, url))
    return 1 if failures else 0


# --------------------------------------------------------------------------------------------
# service (macOS launchd agent / Linux systemd user unit for the dashboard)
# --------------------------------------------------------------------------------------------

SERVICE_LABEL = "io.body-os.dashboard"


def service_plist_path():
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", SERVICE_LABEL + ".plist")


def service_plist(ctx, port, lan):
    o = ctx.opts
    argv = [sys.executable, os.path.abspath(__file__)]
    for flag in ("me", "data", "household"):
        if o.get(flag):
            argv += ["--" + flag, os.path.abspath(o[flag])]
    argv += ["dashboard", "--port", str(port)] + (["--lan"] if lan else [])
    log = os.path.join(ctx.data, "dashboard.log")
    return {"Label": SERVICE_LABEL, "ProgramArguments": argv, "RunAtLoad": True, "KeepAlive": True,
            "WorkingDirectory": ROOT, "StandardOutPath": log, "StandardErrorPath": log,
            "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"}, "ProcessType": "Background"}


def _launchctl(cmd, dry_run):
    print("$ " + " ".join(cmd))
    if dry_run:
        return 0
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:
        print("  %s" % e)
        return 1
    out = (r.stdout + r.stderr).strip()
    if out:
        print("  " + out.replace("\n", "\n  "))
    return r.returncode


def _port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


SYSTEMD_UNIT = "body-os-dashboard.service"


def systemd_unit(ctx, port, lan):
    argv = [sys.executable, os.path.abspath(__file__)]
    for flag in ("me", "data", "household"):
        if ctx.opts.get(flag):
            argv += ["--" + flag, os.path.abspath(ctx.opts[flag])]
    argv += ["dashboard", "--port", str(port)] + (["--lan"] if lan else [])
    return ("[Unit]\nDescription=body-os dashboard\nAfter=network-online.target\nWants=network-online.target\n\n"
            "[Service]\nWorkingDirectory=%s\nExecStart=%s\nEnvironment=PYTHONUNBUFFERED=1\n"
            "Restart=always\nRestartSec=5\n\n[Install]\nWantedBy=default.target\n" % (ROOT, " ".join(argv)))


def cmd_service_linux(ctx, args):
    path = os.path.join(os.path.expanduser("~"), ".config", "systemd", "user", SYSTEMD_UNIT)
    run = lambda cmd: _launchctl(cmd, args.dry_run)  # same print-and-run helper
    if args.service_cmd == "install":
        unit = systemd_unit(ctx, args.port, args.lan)
        if args.dry_run:
            print("# would write %s\n%s" % (path, unit))
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(unit)
            print("wrote %s" % path)
        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT])
        run(["systemctl", "--user", "restart", SYSTEMD_UNIT])
        user = os.environ.get("USER") or ""
        linger = subprocess.run(["loginctl", "show-user", user, "-p", "Linger"], capture_output=True, text=True) \
            if not args.dry_run else None
        if linger is not None and "Linger=yes" not in linger.stdout:
            print("NOTE: to keep the dashboard running after logout/reboot, run once (needs your password):\n"
                  "  sudo loginctl enable-linger %s" % user)
        print("dashboard service: http://127.0.0.1:%d/%s" % (args.port, " - LAN on" if args.lan else ""))
        return 0
    if args.service_cmd == "uninstall":
        run(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT])
        if not args.dry_run and os.path.exists(path):
            os.remove(path)
            print("removed %s" % path)
        run(["systemctl", "--user", "daemon-reload"])
        return 0
    r = subprocess.run(["systemctl", "--user", "is-active", SYSTEMD_UNIT], capture_output=True, text=True) \
        if not args.dry_run else None
    active = bool(r) and r.stdout.strip() == "active"
    print("unit:    %s" % (path if os.path.exists(path) else "not installed"))
    print("systemd: %s" % (r.stdout.strip() if r else "(dry run)"))
    print("port:    %d %s" % (args.port, "responds" if _port_open(args.port) else "does not respond"))
    return 0 if active else 1


def cmd_service(ctx, args):
    import plistlib
    if sys.platform.startswith("linux"):
        return cmd_service_linux(ctx, args)
    if sys.platform != "darwin":
        raise BosError("`bos service` supports macOS (launchd) and Linux (systemd --user)")
    path = service_plist_path()
    domain = "gui/%d" % os.getuid()
    if args.service_cmd == "install":
        pl = service_plist(ctx, args.port, args.lan)
        data = plistlib.dumps(pl).decode("utf-8")
        if args.dry_run:
            print("# would write %s\n%s" % (path, data))
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.makedirs(ctx.data, exist_ok=True)
            os.close(os.open(pl["StandardOutPath"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600))
            os.chmod(pl["StandardOutPath"], 0o600)
            if os.path.exists(path):
                _launchctl(["launchctl", "bootout", "%s/%s" % (domain, SERVICE_LABEL)], False)
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            print("wrote %s" % path)
        if _launchctl(["launchctl", "bootstrap", domain, path], args.dry_run) != 0:
            _launchctl(["launchctl", "load", "-w", path], args.dry_run)
        print("dashboard service: http://127.0.0.1:%d/ (log: %s)%s" % (
            args.port, pl["StandardOutPath"], " - LAN on; see /devices for the phone link" if args.lan else ""))
        if args.lan:
            print("note: macOS may ask whether Python may accept incoming connections - allow it. "
                  "The Mac must be awake for phones to reach it.")
        return 0
    if args.service_cmd == "uninstall":
        if _launchctl(["launchctl", "bootout", "%s/%s" % (domain, SERVICE_LABEL)], args.dry_run) != 0:
            _launchctl(["launchctl", "unload", "-w", path], args.dry_run)
        if args.dry_run:
            print("# would remove %s" % path)
        elif os.path.exists(path):
            os.remove(path)
            print("removed %s" % path)
        return 0
    # status
    port = args.port
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                argv = plistlib.load(f).get("ProgramArguments") or []
            if "--port" in argv:
                port = int(argv[argv.index("--port") + 1])
        except (OSError, ValueError, IndexError, plistlib.InvalidFileException):
            pass
        print("plist:   %s" % path)
    else:
        print("plist:   not installed (%s)" % path)
    if args.dry_run:
        print("$ launchctl print %s/%s" % (domain, SERVICE_LABEL))
        return 0
    try:
        r = subprocess.run(["launchctl", "print", "%s/%s" % (domain, SERVICE_LABEL)], capture_output=True, text=True)
        loaded = r.returncode == 0
        state = re.search(r"^\s*state = (.+)$", r.stdout, re.M)
    except OSError:
        loaded, state = False, None
    print("launchd: %s" % (("loaded, " + state.group(1).strip()) if loaded and state else "loaded" if loaded else "not loaded"))
    print("port:    %d %s" % (port, "responds" if _port_open(port) else "does not respond"))
    return 0 if loaded else 1


# --------------------------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------------------------

def cmd_doctor(ctx, args):
    fails = warns = 0

    def report(level, msg):
        nonlocal fails, warns
        fails += level == "FAIL"
        warns += level == "WARN"
        print("%-4s %s" % (level, msg))

    def check_private(path, label):
        """Own git repo, no remote, ignored by the engine repo when inside it."""
        if is_own_repo(path):
            report("OK", "%s is its own git repository" % label)
            names = [n for n in git(["remote"], path).stdout.split() if n]
            urls = {n: git(["remote", "get-url", n], path).stdout.strip() for n in names}
            foreign = {n: u for n, u in urls.items() if not is_home_remote(u, sync_allowed_hosts(ctx))}
            if foreign:
                report("WARN", "!!! %s HAS A REMOTE OUTSIDE THE HOME NETWORK - personal health data could leave "
                               "home. Remove it unless deliberate:\n     %s" % (
                                   label, "\n     ".join("%s %s" % kv for kv in foreign.items())))
            elif urls:
                report("OK", "%s syncs only within the home network (%s)" % (label, ", ".join(urls.values())))
            else:
                report("OK", "%s has no remote" % label)
        else:
            report("FAIL", "%s is not its own git repository - run `git init` in it (or `bos.py init`)" % label)
        if os.path.realpath(path).startswith(os.path.realpath(ctx.root) + os.sep):
            r = git(["check-ignore", "-q", os.path.relpath(path, ctx.root) + "/"], ctx.root)
            if r.returncode == 0:
                report("OK", "%s is git-ignored by the engine repo" % label)
            else:
                report("FAIL", "%s is NOT ignored by the engine repo - check .gitignore" % label)
        else:
            report("OK", "%s is outside the engine repo" % label)

    def check_instance(c, label):
        if not os.path.isdir(c.me):
            report("FAIL", "no instance folder at %s - run `bos.py init`%s" % (
                c.me, "" if not c.member else " or `bos.py profile add`"))
            return
        report("OK", "instance folder %s" % c.me)
        check_private(c.me, label)
        problems = validate_all(c)
        if problems:
            report("FAIL", "%d data problem(s) in %s; run `bos.py%s validate`" % (
                len(problems), label, " --profile " + c.member["id"] if c.member else ""))
        else:
            report("OK", "%s jsonl files valid" % label)

    if ctx.household:
        hdir = ctx.household_dir
        report("OK", "household mode: %s (%d member(s))" % (hdir, len(ctx.household["members"])))
        check_private(hdir, "household/")
        if not ctx.member:
            report("WARN", "no default member: set default_member in household.json (or keep a member at me/)")
        for m in ctx.household["members"]:
            c = ctx.for_profile(m["id"])
            label = "%s/ (%s%s)" % (m["path"].strip("/"), m["id"], "" if m["consent"] else ", no consent yet")
            check_instance(c, label)
            for rel in SHARED_FILES:
                mine, shared = os.path.join(c.me, rel), os.path.join(hdir, rel)
                if os.path.exists(mine) and os.path.exists(shared):
                    report("WARN", "both household/%s and %s/%s exist - the household copy is used; merge and "
                                   "remove the member copy" % (rel, m["path"].strip("/"), rel))
        kpath = os.path.join(hdir, "server.json")
    else:
        check_instance(ctx, os.path.relpath(ctx.me, ctx.base) + "/")
        kpath = os.path.join(ctx.data, "server.json")
    if os.path.exists(kpath):
        mode = os.stat(kpath).st_mode & 0o777
        report("OK" if not mode & 0o077 else "WARN", "household key %s (mode %o%s)" % (
            kpath, mode, "" if not mode & 0o077 else " - run chmod 600"))
    hp = git(["config", "--get", "core.hooksPath"], ctx.root).stdout.strip()
    if hp == ".githooks":
        report("OK", "engine hooks enabled (core.hooksPath=.githooks)")
    else:
        report("FAIL", "engine hooks not enabled - run `git config core.hooksPath .githooks` (or `bos.py init`)")
    for h in ("pre-commit", "pre-push"):
        p = os.path.join(ctx.root, ".githooks", h)
        if not (os.path.isfile(p) and os.access(p, os.X_OK)):
            report("FAIL", ".githooks/%s missing or not executable" % h)
    for d in ("data/", "people/", "household/"):
        r = git(["check-ignore", "-q", d], ctx.root)
        report("OK" if r.returncode == 0 else "FAIL", "%s is %sgit-ignored" % (d, "" if r.returncode == 0 else "NOT "))
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
    p.add_argument("--household", help="household folder (default: <repo>/household; with --me only if given)")
    p.add_argument("--profile", help="household member id whose instance folder to use "
                                     "(default: household default_member, else me/)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create me/ from templates/me, git init it, enable engine hooks")
    sub.add_parser("doctor", help="check privacy guards and data validity")

    for name, hlp in (("log", "append health event(s) to me/log/YYYY/YYYY-MM.jsonl"),
                      ("pantry-log", "append pantry event(s) to pantry/pantry.jsonl (household/ in household mode)")):
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
    sp = sub.add_parser("dashboard", help="serve the dashboard (live, read-only) on 127.0.0.1, or the LAN with --lan")
    sp.add_argument("--port", type=int, default=8030)
    sp.add_argument("--days", choices=DASHBOARD_PERIODS, default="30", help="default period (14/30/90/all)")
    sp.add_argument("--lan", action="store_true", help="listen on all interfaces; other devices need the household key")
    sp.add_argument("--rotate-key", action="store_true", help="replace the household key (re-pair every device)")

    sp = sub.add_parser("household", help="household mode: shared kitchen for several members")
    hsub = sp.add_subparsers(dest="household_cmd", required=True)
    hi = hsub.add_parser("init", help="create household/ (private git repo), register me/, move the kitchen there")
    hi.add_argument("--name", help="household name shown in the dashboard")
    hi.add_argument("--member-id", help="id for the existing me/ instance, e.g. alex")
    hi.add_argument("--member-name", help="display name for the existing me/ instance")
    hi.add_argument("--color", choices=MEMBER_COLORS, help="avatar colour for the existing me/ instance")

    sp = sub.add_parser("profile", help="household members: add / list / consent")
    psub = sp.add_subparsers(dest="profile_cmd", required=True)
    pa = psub.add_parser("add", help="create a member instance (people/<id>/) from templates/me and register it")
    pa.add_argument("id")
    pa.add_argument("--name", required=True)
    pa.add_argument("--color", choices=MEMBER_COLORS)
    pa.add_argument("--path", help="instance folder relative to the engine root (default people/<id>)")
    pa.add_argument("--language", choices=("de", "en"), help="default: household language")
    g = pa.add_mutually_exclusive_group()
    g.add_argument("--consent", dest="consent", action="store_true", help="member already agreed (default: no)")
    g.add_argument("--no-consent", dest="consent", action="store_false", help="default: nothing is logged yet")
    pa.set_defaults(consent=False)
    pl = psub.add_parser("list", help="list members")
    pl.add_argument("--json", action="store_true")
    pc = psub.add_parser("consent", help="record that a member agreed to tracking (after their interview)")
    pc.add_argument("id")
    pc.add_argument("--revoke", action="store_true", help="withdraw consent: nothing new is logged")

    sp = sub.add_parser("sync", help="home server sync of the private repos (pull, then push)")
    sp.add_argument("--pull-only", action="store_true")
    sp.add_argument("--push-only", action="store_true")
    syn = sp.add_subparsers(dest="sync_cmd")
    ss = syn.add_parser("setup", help="create the private repos on a home server and add `home` remotes")
    ss.add_argument("--host", required=True, help="ssh target on the home network, e.g. fabian@faberry.local")
    ss.add_argument("--path", default="body-os", help="engine folder on the server (relative to its home)")
    ss.add_argument("--engine-url", help="git URL of the engine to clone on the server (default: GitHub)")
    ss.add_argument("--force", action="store_true", help="allow a host that does not look like a home address")
    ss.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("service", help="run the dashboard in the background (macOS launchd / Linux systemd --user)")
    ssub = sp.add_subparsers(dest="service_cmd", required=True)
    for name, hlp in (("install", "write ~/Library/LaunchAgents/%s.plist and load it" % SERVICE_LABEL),
                      ("uninstall", "unload and remove the launchd agent"),
                      ("status", "is the agent loaded and does the port respond?")):
        sc = ssub.add_parser(name, help=hlp)
        sc.add_argument("--port", type=int, default=8030)
        sc.add_argument("--dry-run", action="store_true", help="print the plist and commands only")
        if name == "install":
            sc.add_argument("--lan", action="store_true", help="serve the LAN with the household key")

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
                "dash": cmd_dash, "dashboard": cmd_dashboard, "foods-import": cmd_foods_import}
    try:
        ctx = Ctx(args.me, args.data, args.today, args.household, args.profile)
        if args.cmd == "household":
            return cmd_household_init(ctx, args)
        if args.cmd == "profile":
            return {"add": cmd_profile_add, "list": cmd_profile_list, "consent": cmd_profile_consent}[
                args.profile_cmd](ctx, args)
        if args.cmd == "service":
            return cmd_service(ctx, args)
        if args.cmd == "sync":
            return cmd_sync_setup(ctx, args) if args.sync_cmd == "setup" else cmd_sync(ctx, args)
        if args.cmd == "food":
            return cmd_food_search(ctx, args) if args.food_cmd == "search" else cmd_food_calc(ctx, args)
        return handlers[args.cmd](ctx, args)
    except BosError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
