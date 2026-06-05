#!/usr/bin/env python3
"""mail-to-tasks — turn grounded email action items into GTD inbox tasks (M2).

The **timer/debug entrypoint** for the email→GTD pipeline; the work lives in
``life_agent.tasks.project.project_action_items``. By default it does the whole
chain — **extract** (run the pkm ``action_items`` transform over new emails, the
local-model cost step) then **project** (file each fresh, grounded item once into
the in-tree jarvis GTD inbox with a ``[src:email <Message-ID>]`` citation) — and
pings Telegram. The grounded extraction is the safety gate; you triage in the
Telegram bot (``list inbox`` / ``delete`` / ``move``). Process-once via a ledger,
so a task you clear never returns.

This is meant to run unattended from a ``systemd --user`` timer after mail
ingest; running it by hand is for debugging. Use ``--dry-run`` to preview the
grounded candidates without extracting or writing anything.

    uv run --project . python scripts/mail_to_tasks.py             # extract + file + notify
    uv run --project . python scripts/mail_to_tasks.py --dry-run   # preview only, write nothing
    uv run --project . python scripts/mail_to_tasks.py --no-extract --no-notify
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
    # Run both transforms over the (recent) emails: email_triage classifies each
    # (SPEC §18.8), action_items extracts grounded to-dos (§18.6). They compose at
    # the projection layer — a task is filed only from an email triaged actionable.
    # `--config` is a global pkm arg (before the subcommand); `--limit` is a
    # `transform run` arg (after the name). Order matters.
    for name in ("email_triage", "action_items"):
        cmd = [
            sys.executable, "-m", "pkm", "--config", str(C.PKM_CONFIG),
            "transform", "run", name,
        ]
        if limit is not None:
            cmd += ["--limit", str(limit)]
        print(f"→ extracting {name}: {' '.join(cmd[2:])}")
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            # Don't crash — projection of already-cached artifacts can still run —
            # but never let the timer silently extract nothing.
            print(
                f"⚠ {name} exited {proc.returncode}; projecting already-cached artifacts only",
                file=sys.stderr,
            )


def _print_candidate(c: Candidate) -> None:
    print(f"\n• {c.action_phrase}")
    print(f"    quote: “{c.source_quote}”")
    print(f"    cite:  {c.citation}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="preview grounded candidates; extract nothing, write nothing",
    )
    ap.add_argument(
        "--no-extract", action="store_true",
        help="skip the pkm transform; project already-cached artifacts",
    )
    ap.add_argument(
        "--no-notify", action="store_true", help="file tasks but skip the Telegram nudge",
    )
    ap.add_argument("--limit", type=int, help="cap the number of emails extracted / artifacts read")
    ap.add_argument("--since", type=str, help="only artifacts extracted on/after YYYY-MM-DD")
    args = ap.parse_args()

    commit = not args.dry_run
    if commit and not args.no_extract:
        _run_extract(args.limit)

    root = pkm_root()
    since = datetime.fromisoformat(args.since) if args.since else None
    user_id = _resolve_user_id(C.JARVIS_DB_PATH) if commit else 0

    report = project_action_items(
        root,
        db_path=C.JARVIS_DB_PATH,
        user_id=user_id,
        ledger=C.TASKS_LEDGER,
        commit=commit,
        notify=not args.no_notify,
        limit=args.limit,
        since=since,
    )

    already = report.total_items - len(report.fresh)
    print(
        f"{report.total_emails} actionable email(s) with items "
        f"({report.nonactionable_filtered} non-actionable filtered by triage); "
        f"{report.total_items} item(s), {len(report.fresh)} fresh "
        f"({already} already filed)."
    )
    for c in report.fresh:
        _print_candidate(c)

    if not report.fresh:
        print("\nNothing to file.")
        return 0
    if args.dry_run:
        print("\nDRY RUN — nothing written. Drop --dry-run to file these to your GTD inbox.")
        return 0

    print(f"\nFiled {report.filed} task(s) to the GTD inbox; ledger updated.")
    if report.notified:
        print("Telegram nudge sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
