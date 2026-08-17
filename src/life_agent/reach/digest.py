"""Daily digest — a morning summary over the GTD projection, sent via Telegram.

Reads the read-model (``tasks.store``) and speaks in the digest voice; runs from a
``systemd --user`` timer (``packaging/daily-digest.timer`` → ``bin/daily-digest``).
Reach, not truth — outbound only, parses nothing (interaction contract §push).
"""

from __future__ import annotations

from datetime import date

from life_agent.reach import telegram
from life_agent.tasks.store import get_db, owner_user_id

# How many #next tasks the digest shows before naming the remainder.
NEXT_LIMIT = 5

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
}


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

    if not any([today_tasks, overdue, due_today, next_tasks]) and inbox_count == 0:
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
