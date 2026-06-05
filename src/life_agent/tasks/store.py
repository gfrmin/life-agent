"""The write seam into the in-tree jarvis GTD store (M2).

A function call, not a cross-repo SQLite write or an MCP round-trip:
``from jarvis import db`` → ``db.add_task``. The jarvis schema is unchanged — the
citation rides in the task text (jarvis has no provenance column, by design for
this MVP). ``db_path`` is explicit so the CLI points at the live store and tests
point at a temp db.
"""

from __future__ import annotations

from pathlib import Path

from life_agent.tasks.policy import Candidate


def add_to_inbox(candidate: Candidate, *, user_id: int, db_path: Path) -> str:
    """File one candidate into the jarvis GTD inbox; returns jarvis's reply string."""
    from jarvis import db

    # db.DB_PATH is a module var read by get_db(); point it at the configured store.
    db.DB_PATH = Path(db_path)
    db.init_db()  # idempotent (CREATE TABLE IF NOT EXISTS) — robust to a fresh store
    return db.add_task(user_id, candidate.task_text(), "inbox")
