#!/usr/bin/env python3
"""One-time migration: the live jarvis.db rows → the event ledger.

Bootstraps the event-sourced GTD from the pre-event-sourcing SQLite store: each existing
task becomes an ``Asserted`` (human origin) event carrying its current attributes, and each
*completed* task additionally a ``Disposed{done}`` event (stamped with its ``completed_at``).
Then ``fold(ledger)`` reproduces the current task set — which the migration **verifies row
for row** before it touches anything.

Safe by construction:
- ``--dry-run`` (default) builds the events, rebuilds into a temp db, and reports the
  verification — writing nothing.
- ``--commit`` only proceeds if verification passes; it backs up the old db, appends to the
  ledger, and rebuilds the real read-model. It refuses to run if the ledger is already
  populated (the migration is one-shot), unless ``--force``.

    uv run --project . python scripts/migrate_jarvis_to_events.py            # dry-run + verify
    uv run --project . python scripts/migrate_jarvis_to_events.py --commit   # do it
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import life_agent.core as C
from life_agent.tasks import events as ev
from life_agent.tasks import store

# The attributes that define a task's identity-for-verification (id is reassigned by the
# projection, so we compare by content, not by the old autoincrement id).
_ACTIVE_COLS = ("user_id", "text", "list", "due_date", "is_today")


def read_old_tasks(db_path: Path) -> list[dict[str, Any]]:
    """Read the pre-event-sourcing ``tasks`` rows (ordered by id)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, user_id, text, list, due_date, is_today, created_at, completed_at "
            "FROM tasks ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def build_events(rows: list[dict[str, Any]]) -> list[ev.Event]:
    """Each row → an ``Asserted`` (human) event; completed rows → a ``Disposed{done}`` too.

    ``tx_time`` is preserved from ``created_at`` / ``completed_at`` so the rebuilt read-model
    keeps the original timestamps.
    """
    events: list[ev.Event] = []
    for r in rows:
        ident = ev.new_identity()
        events.append(
            ev.asserted(
                ident,
                payload={
                    "user_id": r["user_id"],
                    "text": r["text"],
                    "list": r["list"],
                    "due_date": r["due_date"],
                    "is_today": int(r["is_today"] or 0),
                    "origin": "human",
                },
                tx_time=r["created_at"] or ev.now_iso(),
            )
        )
        if r["completed_at"]:
            events.append(ev.disposed(ident, reason="done", tx_time=r["completed_at"]))
    return events


@dataclass(frozen=True)
class Verification:
    ok: bool
    detail: str


def _snapshot(db_path: Path) -> tuple[list[tuple[Any, ...]], list[str]]:
    """(active rows by content, completed task texts) — the verification invariant."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        active = sorted(
            tuple(r[c] for c in _ACTIVE_COLS)
            for r in conn.execute("SELECT * FROM tasks WHERE completed_at IS NULL")
        )
        completed = sorted(
            r["text"] for r in conn.execute("SELECT text FROM tasks WHERE completed_at IS NOT NULL")
        )
    finally:
        conn.close()
    return active, completed


def _rebuild_into(db_path: Path, events: list[ev.Event]) -> None:
    """Point the store at ``db_path`` and rebuild the read-model from ``events``."""
    original = store.DB_PATH
    store.DB_PATH = db_path
    try:
        store.init_db()
        with store.get_db() as conn:
            store.rebuild(conn, events)
    finally:
        store.DB_PATH = original


def verify(events: list[ev.Event], old_rows: list[dict[str, Any]], tmp_db: Path) -> Verification:
    """Rebuild ``events`` into ``tmp_db`` and confirm it matches the old rows by content."""
    _rebuild_into(tmp_db, events)
    new_active, new_completed = _snapshot(tmp_db)

    old_active = sorted(
        tuple(
            (int(r["is_today"] or 0) if c == "is_today" else r[c]) for c in _ACTIVE_COLS
        )
        for r in old_rows
        if not r["completed_at"]
    )
    old_completed = sorted(r["text"] for r in old_rows if r["completed_at"])

    if new_active == old_active and new_completed == old_completed:
        return Verification(
            True, f"{len(old_active)} active + {len(old_completed)} completed reproduced exactly"
        )
    diff = (
        f"active old={len(old_active)} new={len(new_active)}; "
        f"completed old={len(old_completed)} new={len(new_completed)}"
    )
    return Verification(False, f"MISMATCH — {diff}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="actually migrate (default: dry-run)")
    ap.add_argument("--force", action="store_true", help="proceed even if the ledger is non-empty")
    args = ap.parse_args()

    db_path = C.JARVIS_DB_PATH
    ledger = C.TASKS_LEDGER

    if not db_path.exists():
        print(f"No store at {db_path} — nothing to migrate.")
        return 0
    old_rows = read_old_tasks(db_path)
    events = build_events(old_rows)
    print(f"Read {len(old_rows)} task(s) → {len(events)} event(s).")

    tmp_db = db_path.with_suffix(".migrate-verify.db")
    try:
        result = verify(events, old_rows, tmp_db)
    finally:
        tmp_db.unlink(missing_ok=True)
    print(("✓ " if result.ok else "✗ ") + result.detail)
    if not result.ok:
        print("Aborting — fold(ledger) does not reproduce the current store.", file=sys.stderr)
        return 1

    if not args.commit:
        print("\nDRY RUN — nothing written. Re-run with --commit to migrate.")
        return 0

    if ledger.exists() and ledger.stat().st_size > 0 and not args.force:
        print(
            f"\nLedger {ledger} already populated — migration done? Use --force to override.",
            file=sys.stderr,
        )
        return 1

    backup = db_path.with_suffix(".pre-migration.bak")
    shutil.copy2(db_path, backup)
    print(f"Backed up {db_path} → {backup}")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ev.append(ledger, events)
    _rebuild_into(db_path, events)
    final = verify(events, old_rows, db_path)
    print(("✓ " if final.ok else "✗ ") + f"post-commit: {final.detail}")
    print(f"\nMigrated. Ledger: {ledger}. Read-model rebuilt: {db_path}.")
    return 0 if final.ok else 1


if __name__ == "__main__":
    sys.exit(main())
