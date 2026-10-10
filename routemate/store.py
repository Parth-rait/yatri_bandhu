"""SQLite storage for per-browser data: saved places, trips, feedback, settings, usability tests."""
import json
import sqlite3
import time
import uuid
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "instance" / "routemate.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (uid TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS saved (id TEXT PRIMARY KEY, uid TEXT, label TEXT, icon TEXT, point TEXT, name TEXT, created REAL);
CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, uid TEXT, origin TEXT, dest TEXT, origin_name TEXT, dest_name TEXT,
    mode TEXT, summary TEXT, started REAL, status TEXT);
CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, uid TEXT, trip_id TEXT, rating INTEGER, accurate INTEGER,
    issues TEXT, comment TEXT, created REAL);
CREATE TABLE IF NOT EXISTS study (id TEXT PRIMARY KEY, uid TEXT, participant TEXT, task TEXT, seconds REAL, clicks INTEGER,
    errors INTEGER, outcome TEXT, confidence INTEGER, path TEXT, created REAL);
CREATE TABLE IF NOT EXISTS sus (id TEXT PRIMARY KEY, uid TEXT, participant TEXT, answers TEXT, score REAL, created REAL);
"""

DEFAULT_SETTINGS = dict(large_text=False, high_contrast=False, simple_ui=False, reduce_motion=False,
                        ask_priority=True, default_mode="balanced", max_walk=None, default_from="place:plaksha",
                        onboarded=False, name="", use_location=False)

# (label, icon, point, place name, kind)   kind: home | work | fav (a favourite place to visit)
DEFAULT_SAVED = [("Home", "home", "place:plaksha", "Plaksha University", "home"),
                 ("Elante Mall", "star", "place:elante", "Elante Mall", "fav"),
                 ("Sukhna Lake", "star", "place:sukhna", "Sukhna Lake", "fav")]
KIND_ORDER = {"home": 0, "work": 1, "fav": 2}


def connect():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if "kind" not in {r["name"] for r in con.execute("PRAGMA table_info(saved)")}:
        con.execute("ALTER TABLE saved ADD COLUMN kind TEXT DEFAULT 'fav'")
    return con


def new_id():
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- settings
def get_settings(uid):
    with connect() as con:
        row = con.execute("SELECT data FROM settings WHERE uid=?", (uid,)).fetchone()
    s = dict(DEFAULT_SETTINGS)
    if row:
        s.update(json.loads(row["data"]))
    return s


def save_settings(uid, data):
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (uid, json.dumps(data)))


# ---------------------------------------------------------------- saved places
def saved_places(uid):
    with connect() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM saved WHERE uid=? ORDER BY created", (uid,))]
        if not rows and not con.execute("SELECT 1 FROM settings WHERE uid=?", (uid,)).fetchone():
            for label, icon, point, name, kind in DEFAULT_SAVED:
                con.execute("INSERT INTO saved (id, uid, label, icon, point, name, created, kind) VALUES (?,?,?,?,?,?,?,?)",
                            (new_id(), uid, label, icon, point, name, time.time(), kind))
            con.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (uid, json.dumps(DEFAULT_SETTINGS)))
            rows = [dict(r) for r in con.execute("SELECT * FROM saved WHERE uid=? ORDER BY created", (uid,))]
    for r in rows:
        r["kind"] = r.get("kind") or "fav"
    return sorted(rows, key=lambda r: KIND_ORDER.get(r["kind"], 2))


def add_saved(uid, label, icon, point, name, kind="fav"):
    """Home and Work are unique: saving a new one replaces the old one."""
    with connect() as con:
        if kind in ("home", "work"):
            con.execute("DELETE FROM saved WHERE uid=? AND kind=?", (uid, kind))
        con.execute("INSERT INTO saved (id, uid, label, icon, point, name, created, kind) VALUES (?,?,?,?,?,?,?,?)",
                    (new_id(), uid, label, icon, point, name, time.time(), kind))


def toggle_favourite(uid, point, name):
    """Star / unstar a place. Returns True if it is now a favourite."""
    with connect() as con:
        hit = con.execute("SELECT id FROM saved WHERE uid=? AND point=? AND kind='fav'", (uid, point)).fetchone()
        if hit:
            con.execute("DELETE FROM saved WHERE id=?", (hit["id"],))
            return False
        con.execute("INSERT INTO saved (id, uid, label, icon, point, name, created, kind) VALUES (?,?,?,?,?,?,?,?)",
                    (new_id(), uid, name, "star", point, name, time.time(), "fav"))
        return True


def delete_saved(uid, sid):
    with connect() as con:
        con.execute("DELETE FROM saved WHERE uid=? AND id=?", (uid, sid))


# ---------------------------------------------------------------- trips
def start_trip(uid, origin, dest, origin_name, dest_name, mode, summary):
    tid = new_id()
    with connect() as con:
        con.execute("UPDATE trips SET status='done' WHERE uid=? AND status='active'", (uid,))
        con.execute("INSERT INTO trips VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (tid, uid, origin, dest, origin_name, dest_name, mode, json.dumps(summary), time.time(), "active"))
    return tid


def set_trip_status(uid, tid, status):
    with connect() as con:
        con.execute("UPDATE trips SET status=? WHERE uid=? AND id=?", (status, uid, tid))


def trips(uid, limit=50):
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT t.*, f.rating FROM trips t LEFT JOIN feedback f ON f.trip_id=t.id WHERE t.uid=? "
            "ORDER BY started DESC LIMIT ?", (uid, limit))]
    for r in rows:
        r["summary"] = json.loads(r["summary"])
    return rows


def trip(uid, tid):
    with connect() as con:
        r = con.execute("SELECT * FROM trips WHERE uid=? AND id=?", (uid, tid)).fetchone()
    if r:
        r = dict(r)
        r["summary"] = json.loads(r["summary"])
    return r


def active_trip(uid):
    with connect() as con:
        r = con.execute("SELECT * FROM trips WHERE uid=? AND status='active' ORDER BY started DESC", (uid,)).fetchone()
    if r:
        r = dict(r)
        r["summary"] = json.loads(r["summary"])
    return r


# ---------------------------------------------------------------- feedback & evaluation
def add_feedback(uid, trip_id, rating, accurate, issues, comment):
    with connect() as con:
        con.execute("INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?)",
                    (new_id(), uid, trip_id, rating, accurate, json.dumps(issues), comment, time.time()))


def add_study(uid, **kw):
    with connect() as con:
        con.execute("INSERT INTO study VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (new_id(), uid, kw["participant"], kw["task"], kw["seconds"], kw["clicks"], kw["errors"],
                     kw["outcome"], kw["confidence"], json.dumps(kw["path"]), time.time()))


def add_sus(uid, participant, answers):
    score = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers)) * 2.5
    with connect() as con:
        con.execute("INSERT INTO sus VALUES (?,?,?,?,?,?)",
                    (new_id(), uid, participant, json.dumps(answers), score, time.time()))
    return score


def table(name):
    """All rows of an evaluation table, for CSV export (all participants)."""
    assert name in ("feedback", "study", "sus", "trips")
    with connect() as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM {name} ORDER BY rowid")]
