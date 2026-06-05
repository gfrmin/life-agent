#!/usr/bin/env python3
"""Daily digest sender — runs via cron, independent of any agent session.

Run in-tree: ``python -m jarvis.digest``. Requires ``TELEGRAM_TOKEN`` in the
environment. The token is read lazily so importing the module is side-effect free.
"""

import json
import os
from datetime import date, datetime, timedelta
from urllib.request import Request, urlopen

from .db import get_db


def _telegram_token() -> str:
    return os.environ["TELEGRAM_TOKEN"]


def send_telegram(chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{_telegram_token()}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    urlopen(req, timeout=10)


def build_digest(user_id: int) -> str | None:
    today = date.today().isoformat()
    conn = get_db()

    today_tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL ORDER BY id",
        (user_id,),
    ).fetchall()

    overdue = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date < ? AND completed_at IS NULL ORDER BY due_date",
        (user_id, today),
    ).fetchall()

    due_today = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date = ? AND completed_at IS NULL ORDER BY id",
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
        for t in today_tasks:
            lines.append(f"  [{t['id']}] {t['text']}")
        lines.append("")

    if overdue:
        lines.append("OVERDUE:")
        for t in overdue:
            lines.append(f"  [{t['id']}] {t['text']} (due {t['due_date']})")
        lines.append("")

    if due_today:
        lines.append("DUE TODAY:")
        for t in due_today:
            lines.append(f"  [{t['id']}] {t['text']}")
        lines.append("")

    if next_tasks:
        lines.append("UP NEXT:")
        for t in next_tasks:
            lines.append(f"  [{t['id']}] {t['text']}")
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
                send_telegram(user_id, digest)
            except Exception as e:
                print(f"Failed to send digest to {user_id}: {e}")


if __name__ == "__main__":
    main()
