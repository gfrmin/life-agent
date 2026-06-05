#!/usr/bin/env python3
"""mail-to-tasks — file grounded email action items into the GTD inbox (M2).

Reads cached ``action_items`` artifacts (pkm Phase 1) and files each fresh,
grounded item into the in-tree jarvis GTD **inbox** with a
``[src:email <Message-ID>]`` citation (process-once via a ledger), then
optionally pings Telegram. The grounded extraction is the safety gate; the human
triages in the Telegram bot.

The work lives in ``life_agent.tasks.project.project_action_items`` — this script
is just the CLI/timer entrypoint. **Dry-run by default** (prints each grounded
candidate, writes nothing); ``--commit`` files them. ``--extract`` first runs the
pkm transform over emails (the local-model cost step). Scope with
``--limit`` / ``--since``.

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
from life_agent.tasks.project import Candidate, project_action_items
from life_agent.tasks.read import pkm_root


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
    user_id = _resolve_user_id(C.JARVIS_DB_PATH) if args.commit else 0

    report = project_action_items(
        root,
        db_path=C.JARVIS_DB_PATH,
        user_id=user_id,
        ledger=C.TASKS_LEDGER,
        commit=args.commit,
        notify=not args.no_notify,
        limit=args.limit,
        since=since,
    )

    already = report.total_items - len(report.fresh)
    print(
        f"{report.total_emails} email(s) with action items; "
        f"{report.total_items} item(s), {len(report.fresh)} fresh "
        f"({already} already filed)."
    )
    for c in report.fresh:
        _print_candidate(c)

    if not report.fresh:
        print("\nNothing to file.")
        return 0
    if not args.commit:
        print("\nDRY RUN — nothing written. Re-run with --commit to file these to your GTD inbox.")
        return 0

    print(f"\nFiled {report.filed} task(s) to the GTD inbox; ledger updated.")
    if report.notified:
        print("Telegram nudge sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
