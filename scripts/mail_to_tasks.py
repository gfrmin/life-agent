#!/usr/bin/env python3
"""mail-to-tasks — file grounded email action items into the GTD inbox (M2).

Reads cached ``action_items`` artifacts (pkm Phase 1), dedups by the source
email's Message-ID via a process-once ledger, and — with ``--commit`` — files
each into the in-tree jarvis GTD **inbox** with a ``[src:email <Message-ID>]``
citation, then optionally pings Telegram.

**Dry-run by default** — prints each fresh candidate with its verbatim quote and
citation, and writes nothing. Scope with ``--limit`` / ``--since``; ``--extract``
first runs the pkm transform over emails (the local-model cost step).

Run (from the repo root):
    uv run --project . python scripts/mail_to_tasks.py            # dry run
    uv run --project . python scripts/mail_to_tasks.py --commit   # file them
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import life_agent.core as C
from life_agent.tasks import dedup, notify, store
from life_agent.tasks.policy import Candidate, to_candidates
from life_agent.tasks.read import pkm_root, read_action_items


def _resolve_user_id(db_path: Path) -> int:
    """The GTD user id: JARVIS_USER_ID (env/keyring), else the store's sole user."""
    env = os.environ.get("JARVIS_USER_ID")
    if env:
        return int(env)
    try:
        return int(C.secret("JARVIS_USER_ID"))
    except SystemExit:
        pass
    if db_path.exists():
        rows = sqlite3.connect(db_path).execute(
            "SELECT DISTINCT user_id FROM tasks"
        ).fetchall()
        if len(rows) == 1:
            return int(rows[0][0])
    raise SystemExit(
        "set JARVIS_USER_ID (env or keyring) — could not infer a single user from "
        f"{db_path}"
    )


def _run_extract(limit: int | None) -> None:
    cmd = [
        sys.executable, "-m", "pkm", "transform", "run", "action_items",
        "--config", str(C.PKM_CONFIG),
    ]
    if limit is not None:
        cmd += ["--limit", str(limit)]
    print(f"→ extracting action items: {' '.join(cmd[2:])}")
    subprocess.run(cmd, check=False)


def _print_candidate(c: Candidate) -> None:
    print(f"\n• {c.action_phrase}")
    print(f"    quote: “{c.source_quote}”")
    print(f"    cite:  {c.citation}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="file the tasks (default: dry-run)")
    ap.add_argument("--limit", type=int, help="cap the number of action_items artifacts read")
    ap.add_argument("--since", type=str, help="only artifacts extracted on/after YYYY-MM-DD")
    ap.add_argument("--extract", action="store_true", help="run the pkm transform first")
    ap.add_argument("--no-notify", action="store_true", help="skip the Telegram nudge on --commit")
    args = ap.parse_args()

    if args.extract:
        _run_extract(args.limit)

    root = pkm_root()
    since = datetime.fromisoformat(args.since) if args.since else None
    emails = read_action_items(root, limit=args.limit, since=since)
    candidates = to_candidates(emails)

    seen = dedup.load_seen(C.TASKS_LEDGER)
    fresh = [c for c in candidates if c.dedup_key not in seen]

    print(
        f"{len(emails)} email(s) with action items; {len(candidates)} item(s), "
        f"{len(fresh)} fresh ({len(candidates) - len(fresh)} already filed)."
    )
    for c in fresh:
        _print_candidate(c)

    if not fresh:
        print("\nNothing to file.")
        return 0
    if not args.commit:
        print("\nDRY RUN — nothing written. Re-run with --commit to file these to your GTD inbox.")
        return 0

    user_id = _resolve_user_id(C.JARVIS_DB_PATH)
    filed: list[dict[str, str]] = []
    for c in fresh:
        store.add_to_inbox(c, user_id=user_id, db_path=C.JARVIS_DB_PATH)
        filed.append({"dedup_key": c.dedup_key, "message_id": c.message_id})
    dedup.append_seen(C.TASKS_LEDGER, filed)
    print(f"\nFiled {len(filed)} task(s) to the GTD inbox; ledger updated.")

    if not args.no_notify and notify.maybe_notify(
        f"📥 Added {len(filed)} task(s) to your GTD inbox from email.", chat_id=user_id,
    ):
        print("Telegram nudge sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
