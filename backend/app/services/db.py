"""SQLite persistence (single file on the VM): call records + the customer's journey form as captured by voice."""

import json
import sqlite3
import threading
import time
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "cimet.db"
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    call_id    TEXT PRIMARY KEY,
    lead_id    TEXT,
    status     TEXT,
    started_at REAL,
    updated_at REAL,
    data       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calls_lead ON calls(lead_id);
CREATE TABLE IF NOT EXISTS lead_profile (
    lead_id    TEXT NOT NULL,
    field_id   TEXT NOT NULL,
    value      TEXT,
    source     TEXT,
    call_id    TEXT,
    updated_at REAL,
    PRIMARY KEY (lead_id, field_id)
);
CREATE TABLE IF NOT EXISTS leads (
    id   TEXT PRIMARY KEY,
    pos  INTEGER,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dnc_list (
    number   TEXT PRIMARY KEY,
    source   TEXT,  -- register (ACMA stub) | opt_out (customer said no on a call)
    added_at REAL
);
CREATE TABLE IF NOT EXISTS profile_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id    TEXT NOT NULL,
    field_id   TEXT NOT NULL,
    old_value  TEXT,
    new_value  TEXT,
    call_id    TEXT,
    ts         REAL
);
"""


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(_SCHEMA)
    return _conn


def save_call(call: dict) -> None:
    with _lock:
        _db().execute(
            "INSERT INTO calls(call_id, lead_id, status, started_at, updated_at, data) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(call_id) DO UPDATE SET lead_id=excluded.lead_id, status=excluded.status, "
            "updated_at=excluded.updated_at, data=excluded.data",
            (call["call_id"], call.get("lead_id"), call.get("status"), call.get("started_at"), time.time(), json.dumps(call)),
        )
        _db().commit()


def load_calls() -> list[dict]:
    with _lock:
        return [json.loads(r["data"]) for r in _db().execute("SELECT data FROM calls")]


def upsert_field(lead_id: str, field_id: str, value: str, source: str, call_id: str | None) -> None:
    """Write one captured answer to the customer's profile, keeping an audit trail of every change."""
    with _lock:
        db = _db()
        row = db.execute("SELECT value FROM lead_profile WHERE lead_id=? AND field_id=?", (lead_id, field_id)).fetchone()
        old = row["value"] if row else None
        if old == value and row:
            return
        now = time.time()
        db.execute(
            "INSERT INTO lead_profile(lead_id, field_id, value, source, call_id, updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(lead_id, field_id) DO UPDATE SET value=excluded.value, source=excluded.source, "
            "call_id=excluded.call_id, updated_at=excluded.updated_at",
            (lead_id, field_id, value, source, call_id, now),
        )
        db.execute(
            "INSERT INTO profile_history(lead_id, field_id, old_value, new_value, call_id, ts) VALUES(?,?,?,?,?,?)",
            (lead_id, field_id, old, value, call_id, now),
        )
        db.commit()


def seed_field(lead_id: str, field_id: str, value: str) -> None:
    """Insert a value from the original journey only if nothing is stored yet."""
    with _lock:
        db = _db()
        db.execute(
            "INSERT OR IGNORE INTO lead_profile(lead_id, field_id, value, source, call_id, updated_at) VALUES(?,?,?,?,?,?)",
            (lead_id, field_id, value, "journey", None, time.time()),
        )
        db.commit()


def get_profile(lead_id: str) -> dict[str, dict]:
    with _lock:
        rows = _db().execute("SELECT field_id, value, source, call_id, updated_at FROM lead_profile WHERE lead_id=?", (lead_id,))
        return {r["field_id"]: dict(r) for r in rows}


# --- leads and Do Not Call list (dummy data is loaded by scripts/seed_data.py) ---


def replace_lead(lead: dict, pos: int) -> None:
    with _lock:
        _db().execute(
            "INSERT INTO leads(id, pos, data) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET pos=excluded.pos, data=excluded.data",
            (lead["id"], pos, json.dumps(lead)),
        )
        _db().commit()


def list_leads() -> list[dict]:
    with _lock:
        return [json.loads(r["data"]) for r in _db().execute("SELECT data FROM leads ORDER BY pos")]


def get_lead(lead_id: str) -> dict | None:
    with _lock:
        row = _db().execute("SELECT data FROM leads WHERE id=?", (lead_id,)).fetchone()
        return json.loads(row["data"]) if row else None


def add_dnc(number: str, source: str) -> None:
    with _lock:
        _db().execute("INSERT OR REPLACE INTO dnc_list(number, source, added_at) VALUES(?,?,?)", (number, source, time.time()))
        _db().commit()


def dnc_numbers(source: str | None = None) -> set[str]:
    with _lock:
        q, args = ("SELECT number FROM dnc_list WHERE source=?", (source,)) if source else ("SELECT number FROM dnc_list", ())
        return {r["number"] for r in _db().execute(q, args)}


def clear(*tables: str) -> dict[str, int]:
    """Delete every row from the given tables; returns how many rows each held."""
    allowed = {"calls", "lead_profile", "profile_history", "leads", "dnc_list"}
    counts = {}
    with _lock:
        for t in tables:
            if t not in allowed:
                raise ValueError(t)
            counts[t] = _db().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            _db().execute(f"DELETE FROM {t}")
        _db().commit()
    return counts


def get_history(lead_id: str, limit: int = 100) -> list[dict]:
    with _lock:
        rows = _db().execute("SELECT * FROM profile_history WHERE lead_id=? ORDER BY id DESC LIMIT ?", (lead_id, limit))
        return [dict(r) for r in rows]
