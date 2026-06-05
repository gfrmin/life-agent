"""Jarvis GTD — shared database functions.

The DB path is resolved from the environment so the live database lives OUTSIDE
the repo (the output-gateway invariant): ``JARVIS_DB_PATH`` if set, else
``$LIFE_AGENT_KB/jarvis/jarvis.db`` (default ``~/.life-agent/kb/...``).
``DB_PATH`` stays a module-level variable so tests can monkeypatch it.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

VALID_LISTS = ("inbox", "next", "scheduled", "someday")


def _default_db_path() -> Path:
    env = os.environ.get("JARVIS_DB_PATH")
    if env:
        return Path(env).expanduser()
    kb = os.environ.get("LIFE_AGENT_KB")
    base = Path(kb).expanduser() if kb else Path.home() / ".life-agent/kb"
    return base / "jarvis" / "jarvis.db"


DB_PATH = _default_db_path()


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
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                list TEXT NOT NULL DEFAULT 'inbox',
                due_date TEXT,
                is_today INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_list
            ON tasks (user_id, list) WHERE completed_at IS NULL
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                email TEXT NOT NULL,
                subscribed_at TEXT DEFAULT (datetime('now'))
            )
        """)


def _parse_due_date(s: str | None) -> str | None:
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


def add_task(
    user_id: int,
    text: str,
    list_name: str = "inbox",
    due_date: str | None = None,
    is_today: bool = False,
) -> str:
    if list_name not in VALID_LISTS:
        return f"Invalid list '{list_name}'. Use one of: {', '.join(VALID_LISTS)}"
    parsed_date = _parse_due_date(due_date)
    if due_date and not parsed_date:
        return f"Invalid date '{due_date}'. Use YYYY-MM-DD format."
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, text, list, due_date, is_today) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, list_name, parsed_date, int(is_today)),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    due_info = f" (due {parsed_date})" if parsed_date else ""
    return f"Added [{row['id']}] {text} to #{list_name}{due_info}"


def complete_task(
    user_id: int,
    task_id: int | None = None,
    text_match: str | None = None,
) -> str:
    with get_db() as conn:
        if task_id is not None:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND user_id = ? AND completed_at IS NULL",
                (task_id, user_id),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE tasks SET completed_at = datetime('now'), is_today = 0 WHERE id = ? AND user_id = ?",
                    (task_id, user_id),
                )
        elif text_match:
            row = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL AND text LIKE ? ORDER BY id LIMIT 1",
                (user_id, f"%{text_match}%"),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE tasks SET completed_at = datetime('now'), is_today = 0 WHERE id = ? AND user_id = ?",
                    (row["id"], user_id),
                )
        else:
            return "Specify a task_id or text_match to complete."
    if not row:
        return "Task not found."
    return f"Completed: {row['text']}"


def delete_task(user_id: int, task_id: int) -> str:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
        ).fetchone()
        if not row:
            return "Task not found."
        conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    return f"Deleted: {row['text']}"


def move_task(
    user_id: int,
    task_id: int,
    new_list: str,
    due_date: str | None = None,
) -> str:
    if new_list not in VALID_LISTS:
        return f"Invalid list '{new_list}'. Use one of: {', '.join(VALID_LISTS)}"
    parsed_date = _parse_due_date(due_date)
    if due_date and not parsed_date:
        return f"Invalid date '{due_date}'. Use YYYY-MM-DD format."
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET list = ?, due_date = ? WHERE id = ? AND user_id = ? AND completed_at IS NULL",
            (new_list, parsed_date, task_id, user_id),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
    if not row:
        return "Task not found."
    due_info = f" (due {parsed_date})" if parsed_date else ""
    return f"Moved [{row['id']}] {row['text']} to #{new_list}{due_info}"


def mark_today(user_id: int, task_id: int, is_today: bool = True) -> str:
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET is_today = ? WHERE id = ? AND user_id = ? AND completed_at IS NULL",
            (int(is_today), task_id, user_id),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
    if not row:
        return "Task not found."
    action = "Marked for today" if is_today else "Unmarked from today"
    return f"{action}: [{row['id']}] {row['text']}"


def clear_today(user_id: int) -> str:
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE tasks SET is_today = 0 WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL",
            (user_id,),
        )
    return f"Cleared today flag from {cur.rowcount} tasks."


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
    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date = ? AND completed_at IS NULL ORDER BY id",
            (user_id, today),
        ).fetchall()
    return _format_task_list(rows, "Due today:")


def get_overdue_tasks(user_id: int) -> str:
    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date < ? AND completed_at IS NULL ORDER BY due_date, id",
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
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND completed_at >= ? ORDER BY completed_at DESC",
            (user_id, week_ago),
        ).fetchall()
    return _format_task_list(rows, "Completed this week:")
