"""The GTD read-model: a materialised SQLite projection of ``fold(events)``.

This is the *view*, not the truth — every row is derived from the event ledger
(``events.py``). ``apply`` folds one event into the table incrementally; ``rebuild``
replays the whole ledger from empty (recovery / migration / verification). The read
queries are the GTD surface (lists, today, tags, counts, due, completed) — ported
verbatim from the former ``jarvis/db.py`` and now reading the projection.

Schema is jarvis's ``tasks`` table plus two columns: ``identity`` (the event key linking a
row to its assertion) and ``origin`` (``human`` | ``email``). The autoincrement ``id`` stays
as the human-facing handle the Telegram UI shows ("complete 3").
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from life_agent.core.config import JARVIS_DB_PATH
from life_agent.tasks import events as ev

VALID_LISTS = ("inbox", "next", "scheduled", "someday")
_AMENDABLE = frozenset({"list", "due_date", "is_today"})

# Module-level so tests can monkeypatch it; defaults to the out-of-repo read-model path.
DB_PATH: Path = JARVIS_DB_PATH


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                list TEXT NOT NULL DEFAULT 'inbox',
                due_date TEXT,
                is_today INTEGER DEFAULT 0,
                origin TEXT NOT NULL DEFAULT 'human',
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_user_list "
            "ON tasks (user_id, list) WHERE completed_at IS NULL"
        )


# --- projection: fold one event / rebuild the whole ledger ---------------------


def apply(conn: sqlite3.Connection, event: ev.Event) -> None:
    """Fold a single event into the materialised table."""
    if event.type == "asserted":
        p = event.payload
        conn.execute(
            "INSERT OR IGNORE INTO tasks "
            "(identity, user_id, text, list, due_date, is_today, origin, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.identity,
                int(p["user_id"]),
                str(p["text"]),
                str(p.get("list", "inbox")),
                p.get("due_date"),
                int(p.get("is_today", 0)),
                str(p.get("origin", "human")),
                event.tx_time,
            ),
        )
    elif event.type == "amended":
        fields = {k: v for k, v in event.payload.get("fields", {}).items() if k in _AMENDABLE}
        if fields:
            assignments = ", ".join(f"{col} = ?" for col in fields)
            # Columns are whitelisted against _AMENDABLE above, so the f-string is safe.
            conn.execute(
                f"UPDATE tasks SET {assignments} WHERE identity = ?",
                (*fields.values(), event.identity),
            )
    elif event.type == "disposed":
        if event.reason == "done":
            conn.execute(
                "UPDATE tasks SET completed_at = ?, is_today = 0 WHERE identity = ?",
                (event.tx_time, event.identity),
            )
        else:  # "dropped" (or any other reason) removes the task
            conn.execute("DELETE FROM tasks WHERE identity = ?", (event.identity,))
    elif event.type == "superseded":
        conn.execute("DELETE FROM tasks WHERE identity = ?", (event.identity,))


def rebuild(conn: sqlite3.Connection, events: list[ev.Event]) -> None:
    """Replay the whole ledger from empty — the projection is a pure function of it."""
    conn.execute("DELETE FROM tasks")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tasks'")
    for event in events:
        apply(conn, event)


# --- resolution: map the human-facing id / text back to an assertion -----------


def resolve_by_id(
    conn: sqlite3.Connection, user_id: int, task_id: int, *, active_only: bool = True
) -> sqlite3.Row | None:
    q = "SELECT * FROM tasks WHERE id = ? AND user_id = ?"
    if active_only:
        q += " AND completed_at IS NULL"
    row: sqlite3.Row | None = conn.execute(q, (task_id, user_id)).fetchone()
    return row


def resolve_by_text(conn: sqlite3.Connection, user_id: int, text_match: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL "
        "AND text LIKE ? ORDER BY id LIMIT 1",
        (user_id, f"%{text_match}%"),
    ).fetchone()
    return row


# --- validation + rendering (ported from jarvis/db.py) -------------------------


def parse_due_date(s: str | None) -> str | None:
    from datetime import date

    if not s:
        return None
    try:
        date.fromisoformat(s)
        return s
    except (ValueError, TypeError):
        return None


def _format_task(row: sqlite3.Row) -> str:
    parts = [f"[{row['id']}]"]
    if row["is_today"]:
        parts.append("★")
    parts.append(row["text"])
    parts.append(f"#{row['list']}")
    if row["due_date"]:
        parts.append(f"(due {row['due_date']})")
    return " ".join(parts)


def _format_task_list(rows: list[sqlite3.Row], header: str = "") -> str:
    if not rows:
        return f"{header}\nNo tasks." if header else "No tasks."
    lines = [header] if header else []
    for row in rows:
        lines.append(f"  {_format_task(row)}")
    return "\n".join(lines)


# --- read queries (the GTD projection surface) ---------------------------------


def get_tasks(user_id: int, list_name: str | None = None) -> str:
    with get_db() as conn:
        if list_name:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND list = ? AND completed_at IS NULL ORDER BY id",
                (user_id, list_name),
            ).fetchall()
            header = f"#{list_name}:"
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL ORDER BY list, id",
                (user_id,),
            ).fetchall()
            header = "All tasks:"
    return _format_task_list(rows, header)


def get_today_tasks(user_id: int) -> str:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL ORDER BY list, id",
            (user_id,),
        ).fetchall()
    return _format_task_list(rows, "Today's focus:")


def get_tasks_by_tag(user_id: int, tag: str) -> str:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL AND text LIKE ? ORDER BY list, id",
            (user_id, f"%@{tag}%"),
        ).fetchall()
    return _format_task_list(rows, f"@{tag} tasks:")


def get_tasks_due_today(user_id: int) -> str:
    from datetime import date

    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date = ? "
            "AND completed_at IS NULL ORDER BY id",
            (user_id, today),
        ).fetchall()
    return _format_task_list(rows, "Due today:")


def get_overdue_tasks(user_id: int) -> str:
    from datetime import date

    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date < ? "
            "AND completed_at IS NULL ORDER BY due_date, id",
            (user_id, today),
        ).fetchall()
    return _format_task_list(rows, "Overdue:")


def get_task_counts(user_id: int) -> str:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT list, COUNT(*) as count FROM tasks WHERE user_id = ? AND completed_at IS NULL GROUP BY list",
            (user_id,),
        ).fetchall()
        counts = {row["list"]: row["count"] for row in rows}
        for lst in VALID_LISTS:
            counts.setdefault(lst, 0)
        today_count = conn.execute(
            "SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL",
            (user_id,),
        ).fetchone()["count"]
        counts["today"] = today_count
    lines = ["Task counts:"]
    for lst in VALID_LISTS:
        lines.append(f"  #{lst}: {counts[lst]}")
    lines.append(f"  ★ today: {counts['today']}")
    return "\n".join(lines)


def get_completed_this_week(user_id: int) -> str:
    from datetime import datetime, timedelta

    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND completed_at >= ? ORDER BY completed_at DESC",
            (user_id, week_ago),
        ).fetchall()
    return _format_task_list(rows, "Completed this week:")
