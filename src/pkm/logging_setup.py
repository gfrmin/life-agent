"""JSONL logging (SPEC §10).

One file per local-date at ``<root>/logs/<YYYY-MM-DD>.jsonl``. Each
line is a JSON object with the following fields in this order:

  - ``timestamp``   — ISO 8601 with explicit UTC offset, e.g.
                      ``2026-04-19T18:59:40.123456+00:00``.
  - ``level``       — DEBUG | INFO | WARNING | ERROR.
  - ``component``   — the logger name (e.g. ``pkm.catalogue``).
  - ``event``       — short snake_case identifier (from ``extra=``;
                      ``null`` if a call site omitted it).
  - (any event-specific fields supplied via ``extra=``)
  - ``message``     — the human-readable message string.

Field ordering is deliberate: humans read log files top-to-bottom
and identifying fields (timestamp, level, component, event) scan
better when they come before the potentially long ``message``.

Timestamp is produced in the formatter via ``datetime.now(UTC)``.
This is intentionally timezone-explicit — logs are consumed by
external tools and humans for whom tz-ambiguous timestamps are a
foot-gun. It differs from the catalogue's naive-UTC convention
(internal machinery, documented there), and the difference is
intended: don't "harmonise" them.

File naming uses the local date (for human "when did I run this"
reasoning). Line timestamps inside are UTC (for event correlation).
These are separate concerns and the mismatch is deliberate.

No rotation in Phase 1 — each day gets a file, the file grows.
Absurdly large daily files are a signal (e.g., an extract run
logging hundreds of MB), not something to silently rotate away.

Log level conventions (established here so producers 7c+ follow
them without thinking):

  - DEBUG    — frequent no-ops (cache hits, sweep-found-nothing).
  - INFO     — successful state changes (ingested, extracted,
               migration applied).
  - WARNING  — skip-and-continue cases (unreadable path, extraction
               failure recorded in catalogue).
  - ERROR    — things that stop the operation (corrupted meta.json
               during rebuild, version mismatch at startup).

No CRITICAL — overkill for a local tool.

Handler lifecycle: ``setup_logging(root, level)`` is called from
``pkm.cli.main`` exactly once per CLI invocation, after the config
is loaded and before the subcommand handler runs. No module-level
``logging.basicConfig()`` anywhere in the codebase; any file that
adds a handler outside this module is a violation.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# Attributes that Python's logging machinery sets on every
# LogRecord. Anything outside this set was added via ``extra=`` and
# counts as an event-specific field to be surfaced in the JSONL
# output. The list is documented at
# https://docs.python.org/3/library/logging.html#logrecord-attributes;
# mirrored here so the formatter does not depend on private internals.
_RESERVED_LOG_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonlFormatter(logging.Formatter):
    """Formats LogRecords as single-line JSON objects (SPEC §10).

    Emits the fields in a fixed order: ``timestamp``, ``level``,
    ``component``, ``event``, then event-specific fields from
    ``extra=`` (in insertion order), then ``message``.
    """

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "event": getattr(record, "event", None),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key == "event":
                continue
            obj[key] = value
        obj["message"] = record.getMessage()
        return json.dumps(obj, ensure_ascii=False, sort_keys=False)


def log_file_path(root: Path, *, for_date: date | None = None) -> Path:
    """Return the JSONL log file path inside ``root``.

    Uses the local-date convention from SPEC §10: the file is named
    after the day the invocation runs, not the UTC date, so a
    "yesterday's run" is filed where the human expects it. Each
    line's ``timestamp`` inside is UTC regardless.

    Args:
        root: Knowledge root. The ``logs`` subdirectory is created
            on first call.
        for_date: Override for the date component of the filename.
            Defaults to ``date.today()``. Primarily a test seam.
    """
    d = for_date if for_date is not None else date.today()
    return root / "logs" / f"{d.isoformat()}.jsonl"


def setup_logging(root: Path, level: int) -> None:
    """Install the JSONL file handler on the root logger (SPEC §10).

    Idempotent within a process: repeated calls remove any
    previously-installed JSONL handler before installing the new
    one, so switching log levels or pointing at a different root
    works without accumulating handlers. Handlers added by external
    consumers (e.g. pytest's ``caplog``) are left alone — they use
    a different formatter and are identified by that difference.

    Args:
        root: Knowledge root. ``<root>/logs/`` is created if absent.
        level: Integer log level (e.g. ``logging.INFO``). Applied to
            the root logger; module-level ``logging.getLogger(__name__)``
            calls inherit from there.
    """
    path = log_file_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if isinstance(h.formatter, JsonlFormatter):
            root_logger.removeHandler(h)
            h.close()

    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    handler.setFormatter(JsonlFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
