"""The shared append-only JSONL-log mechanics — durable append, order-defined read.

Three calibration logs share this: the outcomes log (:mod:`life_agent.core.outcomes`),
the decision log (:mod:`life_agent.core.decisions`), and the reaction log
(:mod:`life_agent.core.reactions`). Each keeps its own typed event + (de)serialisation;
only the file mechanics live here — extracted when the third log arrived (the
"two logs is duplication, the third extracts the helper" note in ``decisions.py``).

The discipline these enforce (bayesian-foundations §2/§8): **append-only** (the file is
opened ``"a"`` and never rewritten — an event not logged when it happened is evidence
destroyed), **order-defined** (file order is the canonical replay order; nothing sorts),
and **durable** (flush + fsync — this is an evidence log).
"""
from __future__ import annotations

import os
from pathlib import Path


def append_line(path: Path, line: str) -> None:
    """Append one already-serialised line, durably (flush + fsync). Creates the parent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_lines(path: Path) -> list[str]:
    """Every non-empty line in file order — the canonical replay order. A missing file
    means no evidence yet (empty list); blank lines are skipped, never sorted."""
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]
