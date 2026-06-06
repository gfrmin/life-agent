"""GTD commands — the event-sourced write layer (replaces ``jarvis/db.py``'s writes).

Each command validates, appends event(s) to the ledger (``events.py``, the truth), folds
them into the read-model (``store.apply``), and returns the same human-readable reply the
old ``jarvis/db.py`` returned — the strings the Telegram bot sends back. The ledger write
comes first; the projection is a derived view that a ``store.rebuild`` can always recover.

Identity is origin-aware: a human command mints a unique identity (typing the same task
twice means two tasks); an email-derived assertion passes its content identity in, so a
re-derivation dedups (``store.apply`` is an ``INSERT OR IGNORE`` on identity).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from life_agent.core.config import TASKS_LEDGER
from life_agent.tasks import events as ev
from life_agent.tasks import store
from life_agent.tasks.store import VALID_LISTS

# Module-level so tests can monkeypatch it; defaults to the out-of-repo ledger path.
LEDGER_PATH: Path = TASKS_LEDGER


def _emit(conn: sqlite3.Connection, event: ev.Event) -> None:
    """Append the event to the ledger (truth) then fold it into the read-model (view)."""
    ev.append(LEDGER_PATH, [event])
    store.apply(conn, event)


def add(
    user_id: int,
    text: str,
    list_name: str = "inbox",
    due_date: str | None = None,
    is_today: bool = False,
    *,
    identity: str | None = None,
    origin: str = "human",
    valid_time: str | None = None,
) -> str:
    if list_name not in VALID_LISTS:
        return f"Invalid list '{list_name}'. Use one of: {', '.join(VALID_LISTS)}"
    parsed = store.parse_due_date(due_date)
    if due_date and not parsed:
        return f"Invalid date '{due_date}'. Use YYYY-MM-DD format."
    ident = identity or ev.new_identity()
    event = ev.asserted(
        ident,
        payload={
            "user_id": user_id,
            "text": text,
            "list": list_name,
            "due_date": parsed,
            "is_today": int(is_today),
            "origin": origin,
        },
        valid_time=valid_time,
    )
    with store.get_db() as conn:
        _emit(conn, event)
        row = conn.execute("SELECT id FROM tasks WHERE identity = ?", (ident,)).fetchone()
    rid = row["id"] if row else "?"
    due_info = f" (due {parsed})" if parsed else ""
    return f"Added [{rid}] {text} to #{list_name}{due_info}"


def complete(user_id: int, task_id: int | None = None, text_match: str | None = None) -> str:
    with store.get_db() as conn:
        if task_id is not None:
            row = store.resolve_by_id(conn, user_id, task_id, active_only=True)
        elif text_match:
            row = store.resolve_by_text(conn, user_id, text_match)
        else:
            return "Specify a task_id or text_match to complete."
        if not row:
            return "Task not found."
        _emit(conn, ev.disposed(row["identity"], reason="done"))
        text = row["text"]
    return f"Completed: {text}"


def delete(user_id: int, task_id: int) -> str:
    with store.get_db() as conn:
        row = store.resolve_by_id(conn, user_id, task_id, active_only=False)
        if not row:
            return "Task not found."
        _emit(conn, ev.disposed(row["identity"], reason="dropped"))
        text = row["text"]
    return f"Deleted: {text}"


def move(user_id: int, task_id: int, new_list: str, due_date: str | None = None) -> str:
    if new_list not in VALID_LISTS:
        return f"Invalid list '{new_list}'. Use one of: {', '.join(VALID_LISTS)}"
    parsed = store.parse_due_date(due_date)
    if due_date and not parsed:
        return f"Invalid date '{due_date}'. Use YYYY-MM-DD format."
    with store.get_db() as conn:
        row = store.resolve_by_id(conn, user_id, task_id, active_only=True)
        if not row:
            return "Task not found."
        _emit(conn, ev.amended(row["identity"], {"list": new_list, "due_date": parsed}))
        text = row["text"]
    due_info = f" (due {parsed})" if parsed else ""
    return f"Moved [{task_id}] {text} to #{new_list}{due_info}"


def mark_today(user_id: int, task_id: int, is_today: bool = True) -> str:
    with store.get_db() as conn:
        row = store.resolve_by_id(conn, user_id, task_id, active_only=True)
        if not row:
            return "Task not found."
        _emit(conn, ev.amended(row["identity"], {"is_today": int(is_today)}))
        text = row["text"]
    action = "Marked for today" if is_today else "Unmarked from today"
    return f"{action}: [{task_id}] {text}"


def clear_today(user_id: int) -> str:
    with store.get_db() as conn:
        rows = conn.execute(
            "SELECT identity FROM tasks "
            "WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL",
            (user_id,),
        ).fetchall()
        for r in rows:
            _emit(conn, ev.amended(r["identity"], {"is_today": 0}))
    return f"Cleared today flag from {len(rows)} tasks."
