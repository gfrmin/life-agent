"""Process-once dedup ledger for filed tasks (M2).

An append-only JSONL ledger under ``$LIFE_AGENT_KB/tasks/`` (outside the repo) of
the dedup keys already filed as tasks. **Process-once** semantics: a task the
owner later clears in jarvis stays cleared — the ledger, not a scan of jarvis,
is the source of truth for "already handled", so re-running never re-adds it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def load_seen(ledger: Path) -> set[str]:
    """The set of dedup keys already filed (empty if the ledger doesn't exist)."""
    if not ledger.exists():
        return set()
    seen: set[str] = set()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            seen.add(json.loads(line)["dedup_key"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return seen


def append_seen(ledger: Path, entries: list[dict[str, str]], *, when: str | None = None) -> None:
    """Append filed entries to the ledger (creates the dir on first use).

    Each entry should carry at least ``dedup_key``; ``message_id`` and a
    timestamp are added for forensics.
    """
    if not entries:
        return
    stamp = when or datetime.now().isoformat(timespec="seconds")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps({**e, "filed_at": stamp}, ensure_ascii=False) + "\n")
