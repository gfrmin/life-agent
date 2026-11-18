"""Daily digest — a morning summary over the GTD projection, sent via Telegram.

Reads the read-model (``tasks.store``) and speaks in the digest voice; runs from a
``systemd --user`` timer (``packaging/daily-digest.timer`` → ``bin/daily-digest``).
Reach, not truth — outbound only, parses nothing (interaction contract §push).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta

from life_agent.reach import telegram
from life_agent.tasks.store import get_db, owner_user_id

# How many #next tasks the digest shows before naming the remainder.
NEXT_LIMIT = 5

# Photo scans waiting for review: a status file written by ops' scans-review on the box
# that holds the yo drive (gfrmin/ops scansplitter/README.md) -- the same box this digest
# runs on, since both follow the drive. Its path comes from SCANS_REVIEW_STATUS, set by
# the deploying box (ops' daily-digest drop-in); no path is baked in here. Read-only and
# optional: unset, absent, unreadable or stale (scans-review not running) means no line.
SCANS_STATUS_MAX_AGE = timedelta(hours=48)

# The push-mode vocabulary (interaction contract §push): one table, rendered by
# build_digest and drift-gated in tests/test_reach.py — the contract's enumerated
# sections by name, plus the invariant-3 truncation line (nothing vanishes silently:
# a #next task past the limit is counted, never dropped without a word).
SECTIONS = {
    "focus": "TODAY'S FOCUS:",
    "overdue": "OVERDUE:",
    "due_today": "DUE TODAY:",
    "next": "UP NEXT:",
    "next_more": "  (+{n} more in #next)",
    "inbox": "You have {n} item(s) in your inbox to process.",
    "scans": "PHOTO SCANS: {n} waiting for review at {url}",
}


def scans_waiting() -> tuple[int, str] | None:
    """(count, review URL) of photo scans waiting for review, or None when there is
    nothing to say: no status file, an unreadable one, a stale one, or zero waiting."""
    path = os.environ.get("SCANS_REVIEW_STATUS")
    if not path:
        return None
    try:
        with open(path) as f:
            status = json.load(f)
        waiting, url = int(status["waiting"]), str(status["url"])
        updated = datetime.fromisoformat(status["updated"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    if waiting <= 0 or datetime.now(UTC) - updated > SCANS_STATUS_MAX_AGE:
        return None
    return waiting, url


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
        "SELECT * FROM tasks WHERE user_id = ? AND list = 'next' AND completed_at IS NULL ORDER BY id",
        (user_id,),
    ).fetchall()
    inbox_count = conn.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND list = 'inbox' AND completed_at IS NULL",
        (user_id,),
    ).fetchone()["c"]
    conn.close()
    scans = scans_waiting()

    if not any([today_tasks, overdue, due_today, next_tasks, scans]) and inbox_count == 0:
        return None

    lines = ["Good morning! Here's your daily digest:\n"]
    if today_tasks:
        lines.append(SECTIONS["focus"])
        lines += [f"  [{t['id']}] {t['text']}" for t in today_tasks]
        lines.append("")
    if overdue:
        lines.append(SECTIONS["overdue"])
        lines += [f"  [{t['id']}] {t['text']} (due {t['due_date']})" for t in overdue]
        lines.append("")
    if due_today:
        lines.append(SECTIONS["due_today"])
        lines += [f"  [{t['id']}] {t['text']}" for t in due_today]
        lines.append("")
    if next_tasks:
        lines.append(SECTIONS["next"])
        lines += [f"  [{t['id']}] {t['text']}" for t in next_tasks[:NEXT_LIMIT]]
        if len(next_tasks) > NEXT_LIMIT:
            lines.append(SECTIONS["next_more"].format(n=len(next_tasks) - NEXT_LIMIT))
        lines.append("")
    if inbox_count > 0:
        lines.append(SECTIONS["inbox"].format(n=inbox_count))
    if scans:
        lines.append(SECTIONS["scans"].format(n=scans[0], url=scans[1]))
    return "\n".join(lines)


def main() -> None:
    # the owner convention (JARVIS_USER_ID env/keyring, else the store's sole user) —
    # the same resolution every other surface uses, not a distinct-user scan
    user_id = owner_user_id()
    digest = build_digest(user_id)
    if digest:
        try:
            telegram.send_message(user_id, digest)
        except Exception as e:
            print(f"Failed to send digest to {user_id}: {e}")


if __name__ == "__main__":
    main()
