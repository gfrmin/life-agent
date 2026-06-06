"""Test the one-time jarvis.db → event-ledger migration (`scripts/migrate_jarvis_to_events`).

Builds a pre-event-sourcing (old-schema) store, runs the migration's event-building +
verification, and confirms ``fold(ledger)`` reproduces the active + completed sets exactly.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate_jarvis_to_events as mig

from life_agent.tasks import store


def _old_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, "
        "list TEXT, due_date TEXT, is_today INTEGER, created_at TEXT, completed_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO tasks (user_id, text, list, due_date, is_today, created_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (7, "Inbox A", "inbox", None, 0, "2026-06-01T00:00:00", None),
            (7, "Focus B", "next", None, 1, "2026-06-02T00:00:00", None),
            (7, "Sched C", "scheduled", "2026-07-01", 0, "2026-06-03T00:00:00", None),
            (7, "Done D", "inbox", None, 0, "2026-06-04T00:00:00", "2026-06-05T00:00:00"),
        ],
    )
    conn.commit()
    conn.close()


def test_build_events_shape(tmp_path: Path) -> None:
    _old_db(tmp_path / "old.db")
    events = mig.build_events(mig.read_old_tasks(tmp_path / "old.db"))
    types = [e.type for e in events]
    assert types.count("asserted") == 4  # one per task
    assert types.count("disposed") == 1  # the completed one


def test_verify_reproduces_old_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _old_db(tmp_path / "old.db")
    rows = mig.read_old_tasks(tmp_path / "old.db")
    events = mig.build_events(rows)

    result = mig.verify(events, rows, tmp_path / "verify.db")
    assert result.ok, result.detail

    # the rebuilt read-model holds the 3 active tasks (lists/flags kept), not the completed one
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "verify.db")
    active = store.get_tasks(7)
    assert "Inbox A" in active and "Focus B" in active and "Sched C" in active
    assert "Done D" not in active
    assert "★" in store.get_today_tasks(7)  # Focus B kept its today flag


def test_verify_detects_mismatch(tmp_path: Path) -> None:
    _old_db(tmp_path / "old.db")
    rows = mig.read_old_tasks(tmp_path / "old.db")
    events = mig.build_events(rows)
    events.pop()  # drop the disposed event → completed task would appear active
    result = mig.verify(events, rows, tmp_path / "verify.db")
    assert not result.ok
