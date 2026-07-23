# src/life_agent/trips/store.py
"""The trips read-model: a materialised SQLite projection of fold(TRIPS_LEDGER).

The view, not the truth — every row derives from the event ledger. `rebuild` replays the
whole ledger through fold(); at this scale (hundreds-low-thousands of events) a full rebuild
per write is milliseconds and sidesteps the global nature of fidelity supersession. JSON-LD
is stored VERBATIM (kitinerary's schema is richer + more volatile than we'd design); the
extracted columns exist only for querying and are a cheap re-derivation, never a lossy one.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from life_agent.core.config import TRIPS_DB_PATH
from life_agent.trips.events import Event
from life_agent.trips.fold import Reservation, fold
from life_agent.trips.identity import res_type

DB_PATH: Path = TRIPS_DB_PATH


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservation (
            identity TEXT PRIMARY KEY,
            res_type TEXT NOT NULL,
            title TEXT, start_iso TEXT, start_tz TEXT, end_iso TEXT, end_tz TEXT,
            confirmation TEXT, provider TEXT,
            dep_iata TEXT, arr_iata TEXT, lat REAL, lon REAL,
            cancelled INTEGER NOT NULL DEFAULT 0,
            superseded_by TEXT,
            fidelity TEXT NOT NULL, source_id TEXT, received_at TEXT,
            trip_id TEXT,
            jsonld TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source (
            source_id TEXT PRIMARY KEY, message_id TEXT, path TEXT, sha256 TEXT,
            received_at TEXT, fidelity TEXT, kind TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trip (
            trip_id TEXT PRIMARY KEY, name TEXT, start_date TEXT, end_date TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_res_current "
                 "ON reservation (start_iso) WHERE superseded_by IS NULL")


def init_db() -> None:
    with get_db() as conn:
        create_schema(conn)


# --- column extraction from verbatim JSON-LD ----------------------------------


def _first(rf: Any) -> dict[str, Any]:
    if isinstance(rf, list):
        return rf[0] if rf and isinstance(rf[0], dict) else {}
    return rf if isinstance(rf, dict) else {}


def _iata(place: Any) -> str | None:
    return place.get("iataCode") if isinstance(place, dict) else None


def _project_columns(r: Reservation) -> dict[str, Any]:
    j = r.jsonld
    t = res_type(j)
    rf = j.get("reservationFor")
    seg0 = _first(rf)
    seg_last = _last_seg(rf)
    dep, arr = seg0.get("departureAirport"), seg_last.get("arrivalAirport")
    start = seg0.get("departureTime") or j.get("checkinTime") or j.get("startTime")
    end = seg_last.get("arrivalTime") or j.get("checkoutTime") or j.get("endTime")
    geo = arr.get("geo") if isinstance(arr, dict) else None
    provider = seg0.get("name") or (seg0.get("airline") or {}).get("iataCode") \
        or _first(rf).get("name")
    return {
        "res_type": t,
        "title": seg0.get("name") or j.get("name"),
        "start_iso": _iso(start), "start_tz": _tz(start, seg0.get("departureTime")),
        "end_iso": _iso(end), "end_tz": None,
        "confirmation": j.get("reservationNumber") or (
            (j.get("bookingDetail") or {}).get("bookingReferenceNumber")),
        "provider": provider if isinstance(provider, str) else None,
        "dep_iata": _iata(dep), "arr_iata": _iata(arr),
        "lat": geo.get("latitude") if isinstance(geo, dict) else None,
        "lon": geo.get("longitude") if isinstance(geo, dict) else None,
    }


def _iso(v: Any) -> str | None:
    if isinstance(v, dict):  # schema.org DateTime {"@value": ..., "timezone": ...}
        return v.get("@value")
    return v if isinstance(v, str) else None


def _tz(v: Any, raw: Any) -> str | None:
    if isinstance(raw, dict):
        return raw.get("timezone")
    return None


def _last_seg(rf: Any) -> dict[str, Any]:
    if isinstance(rf, list) and rf and isinstance(rf[-1], dict):
        return rf[-1]
    return _first(rf)


# --- rebuild + upserts --------------------------------------------------------


def rebuild(conn: sqlite3.Connection, events: list[Event]) -> None:
    conn.execute("DELETE FROM reservation")
    for ident, r in fold(events).items():
        cols = _project_columns(r)
        conn.execute(
            "INSERT INTO reservation (identity, res_type, title, start_iso, start_tz, "
            "end_iso, end_tz, confirmation, provider, dep_iata, arr_iata, lat, lon, "
            "cancelled, superseded_by, fidelity, source_id, received_at, jsonld) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ident, cols["res_type"], cols["title"], cols["start_iso"], cols["start_tz"],
             cols["end_iso"], cols["end_tz"], cols["confirmation"], cols["provider"],
             cols["dep_iata"], cols["arr_iata"], cols["lat"], cols["lon"],
             int(r.cancelled), r.superseded_by, r.fidelity, r.source_id, r.received_at,
             json.dumps(r.jsonld, ensure_ascii=False, sort_keys=True)),
        )


def upsert_source(conn: sqlite3.Connection, source_id: str, *, message_id: str | None,
                  path: str | None, sha256: str | None, received_at: str | None,
                  fidelity: str, kind: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO source (source_id, message_id, path, sha256, received_at, "
        "fidelity, kind) VALUES (?,?,?,?,?,?,?)",
        (source_id, message_id, path, sha256, received_at, fidelity, kind))


def upsert_trip(conn: sqlite3.Connection, trip_id: str, *, name: str | None,
                start_date: str | None, end_date: str | None) -> None:
    conn.execute("INSERT OR REPLACE INTO trip (trip_id, name, start_date, end_date) "
                 "VALUES (?,?,?,?)", (trip_id, name, start_date, end_date))


# --- read queries -------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["cancelled"] = bool(d["cancelled"])
    return d


def timeline(limit: int | None = None) -> list[dict[str, Any]]:
    q = ("SELECT * FROM reservation WHERE superseded_by IS NULL "
         "ORDER BY start_iso DESC")
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_db() as conn:
        return [_row_to_dict(r) for r in conn.execute(q).fetchall()]


def get_reservation(identity: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM reservation WHERE identity = ?", (identity,)).fetchone()
    return _row_to_dict(row) if row else None


def now_next(now_iso: str) -> dict[str, Any]:
    with get_db() as conn:
        current = conn.execute(
            "SELECT * FROM reservation WHERE superseded_by IS NULL AND cancelled = 0 "
            "AND start_iso <= ? AND (end_iso IS NULL OR end_iso >= ?) ORDER BY start_iso DESC",
            (now_iso, now_iso)).fetchall()
        nxt = conn.execute(
            "SELECT * FROM reservation WHERE superseded_by IS NULL AND cancelled = 0 "
            "AND start_iso > ? ORDER BY start_iso ASC LIMIT 1", (now_iso,)).fetchone()
    return {"now": [_row_to_dict(r) for r in current],
            "next": _row_to_dict(nxt) if nxt else None}


def search(term: str) -> list[dict[str, Any]]:
    like = f"%{term}%"
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reservation WHERE superseded_by IS NULL AND ("
            "dep_iata LIKE ? OR arr_iata LIKE ? OR confirmation LIKE ? OR provider LIKE ? "
            "OR title LIKE ?) ORDER BY start_iso DESC",
            (like, like, like, like, like)).fetchall()
    return [_row_to_dict(r) for r in rows]
