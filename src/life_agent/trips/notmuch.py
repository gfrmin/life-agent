"""The mailbox selection seam: a subprocess wrapper over the ``notmuch`` binary.

Follows the trips/extract.py precedent — a system binary wrapped as a producer, no new Python
dependency. Unlike extract (which returns ``[]`` for a non-booking and never raises), notmuch
failures RAISE: a missing binary, unreadable index, or malformed query is an operational error
the owner must see, never a silent empty ingest. Selection + fetch only; the bytes it returns
flow into the same extract() seam.
"""
from __future__ import annotations

import subprocess

from life_agent.core.config import NOTMUCH_BINARY

BINARY: str = NOTMUCH_BINARY
_TIMEOUT_SECONDS = 120


class NotmuchError(RuntimeError):
    """A notmuch invocation failed — abort the run loudly (not a silent empty result)."""


def _run(args: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            [BINARY, *args], capture_output=True, timeout=_TIMEOUT_SECONDS, check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise NotmuchError(f"notmuch invocation failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode(errors="replace")[:200]
        raise NotmuchError(f"notmuch exited {completed.returncode}: {detail}")
    return completed.stdout


def search(query: str) -> list[str]:
    """Message-ids matching ``query`` (the ``id:`` prefix stripped). Empty result -> ``[]``."""
    out = _run(["search", "--output=messages", query]).decode(errors="replace")
    ids: list[str] = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        ids.append(line[3:] if line.startswith("id:") else line)
    return ids


def show_raw(msgid: str) -> bytes:
    """Raw RFC-822 bytes for one message. Raises when notmuch yields nothing for the id."""
    out = _run(["show", "--format=raw", f"id:{msgid}"])
    if not out:
        raise NotmuchError(f"notmuch returned no body for id:{msgid}")
    return out
