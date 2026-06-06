"""Daily digest — a morning summary over the GTD projection, sent via Telegram.

Reads the read-model (``tasks.store``) and speaks in the digest voice; runs from a
``systemd --user`` timer: ``python -m life_agent.reach.digest``. Reach, not truth.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from life_agent.reach import telegram
from life_agent.tasks.store import get_db


def build_digest(user_id: int) -> str | None:
    today = date.today().isoformat()
    conn = get_db()

    today_tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL ORDER BY id",
        (user_id,),
    ).fetchall()
    overdue = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date < ? "
        "AND completed_at IS NULL ORDER BY due_date",
        (user_id, today),
    ).fetchall()
    due_today = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date = ? "
        "AND completed_at IS NULL ORDER BY id",
        (user_id, today),
    ).fetchall()
    next_tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND list = 'next' AND completed_at IS NULL ORDER BY id LIMIT 5",
        (user_id,),
    ).fetchall()
    inbox_count = conn.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND list = 'inbox' AND completed_at IS NULL",
        (user_id,),
    ).fetchone()["c"]
    conn.close()

    if not any([today_tasks, overdue, due_today, next_tasks]) and inbox_count == 0:
        return None

    lines = ["Good morning! Here's your daily digest:\n"]
    if today_tasks:
        lines.append("TODAY'S FOCUS:")
        lines += [f"  [{t['id']}] {t['text']}" for t in today_tasks]
        lines.append("")
    if overdue:
        lines.append("OVERDUE:")
        lines += [f"  [{t['id']}] {t['text']} (due {t['due_date']})" for t in overdue]
        lines.append("")
    if due_today:
        lines.append("DUE TODAY:")
        lines += [f"  [{t['id']}] {t['text']}" for t in due_today]
        lines.append("")
    if next_tasks:
        lines.append("UP NEXT:")
        lines += [f"  [{t['id']}] {t['text']}" for t in next_tasks]
        lines.append("")
    if inbox_count > 0:
        lines.append(f"You have {inbox_count} item(s) in your inbox to process.")
    return "\n".join(lines)


def main() -> None:
    conn = get_db()
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    users = conn.execute(
        "SELECT DISTINCT user_id FROM tasks WHERE completed_at IS NULL AND created_at >= ?",
        (thirty_days_ago,),
    ).fetchall()
    conn.close()

    for row in users:
        user_id = row["user_id"]
        digest = build_digest(user_id)
        if digest:
            try:
                telegram.send_message(user_id, digest)
            except Exception as e:
                print(f"Failed to send digest to {user_id}: {e}")


if __name__ == "__main__":
    main()
