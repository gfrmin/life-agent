"""The unified event schema — ``docs/unified-ledger-design.md`` §2.

One typed envelope, one ``format_version``, the source record carried **verbatim** so every
fold adapter is the existing fold applied to ``record``. Identity of an *occurrence* is
``event_id = sha256(canonical_json({source_id, seq, record}))`` (reviewer R11 / owner S2):
source + assignment pair + verbatim record — two content-identical appends are two events,
and derived annotations (``tx_time``) are never hashed. Vocabularies (``source_id``,
``author``) are closed and checked at construction — an unknown value is a loud error,
never a silent new category (the calibration logs' discipline, r00 a.1 #1).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

FORMAT_VERSION = 1

# The twelve migrating sources of tranche 1 (design §1) plus the reserved names of the
# candidate later flavours — reserved so a later tranche cannot silently reuse them for
# something else.
SOURCE_IDS: frozenset[str] = frozenset({
    "calibration.outcomes", "calibration.decisions", "calibration.reactions",
    "calibration.claude_verdicts", "calibration.gather_outcomes", "calibration.corrections",
    "utility.elicitations", "act.tasks", "act.trips", "pkm.artifact", "pkm.demand",
    "eval.labels",
})
RESERVED_SOURCE_IDS: frozenset[str] = frozenset({"membrane.shadow", "pkm.telemetry"})

AUTHORS: frozenset[str] = frozenset({"world", "owner", "agent"})
Author = Literal["world", "owner", "agent"]

# kernel_id namespaces (design §2 table; the pkm instrument digest is `instrument:` per Q7)
KERNEL_PREFIXES: frozenset[str] = frozenset({
    "grader", "decide", "owner", "claude-code", "executor", "tasks.project", "trips.ingest",
    "instrument", "derive",
})


def canonical(obj: Any) -> str:
    """The one serialisation used for hashing and for segment lines: sorted keys, no
    whitespace, non-ASCII kept (the calibration logs' convention)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def event_id(source_id: str, seq: int, record: dict[str, Any]) -> str:
    """The occurrence identity — R11: hash over ``(source_id, per-source seq, verbatim record)``."""
    return hashlib.sha256(
        canonical({"source_id": source_id, "seq": seq, "record": record}).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class UnifiedEvent:
    """One event on the unified stream (design §2). ``tx_time_raw`` is the source's own stamp
    verbatim; ``tx_time`` is a derived UTC annotation or ``None`` (R4) and is never hashed."""

    source_id: str
    seq: int
    tx_time_raw: str
    kernel_id: str
    author: str
    record: dict[str, Any]
    tx_time: str | None = None
    inputs: tuple[str, ...] = ()
    output: str | None = None
    recorded_draw: dict[str, Any] | None = None
    event_id: str = ""
    format_version: int = field(default=FORMAT_VERSION)

    def __post_init__(self) -> None:
        if self.source_id not in SOURCE_IDS:
            raise ValueError(f"unknown source_id {self.source_id!r} "
                             f"(declared: {sorted(SOURCE_IDS)})")
        if self.author not in AUTHORS:
            raise ValueError(f"unknown author {self.author!r} (declared: {sorted(AUTHORS)})")
        if not isinstance(self.seq, int) or self.seq < 1:
            raise ValueError(f"seq must be a positive int, got {self.seq!r}")
        prefix = self.kernel_id.split(":", 1)[0]
        if prefix not in KERNEL_PREFIXES:
            raise ValueError(f"kernel_id {self.kernel_id!r} outside the declared namespaces "
                             f"{sorted(KERNEL_PREFIXES)}")
        if not isinstance(self.record, dict):
            raise ValueError("record must be the verbatim source record (a JSON object)")
        if self.format_version != FORMAT_VERSION:
            raise ValueError(f"format_version {self.format_version} != {FORMAT_VERSION}")
        expected = event_id(self.source_id, self.seq, self.record)
        if not self.event_id:
            object.__setattr__(self, "event_id", expected)
        elif self.event_id != expected:
            raise ValueError("event_id does not match sha256(source_id, seq, record)")


def to_line(e: UnifiedEvent) -> str:
    """One canonical JSON line (no trailing newline)."""
    d = asdict(e)
    d["inputs"] = list(e.inputs)
    return canonical(d)


def from_line(line: str) -> UnifiedEvent:
    """Parse one segment line; raises on anything malformed (loud by design, §10)."""
    d = json.loads(line)
    d["inputs"] = tuple(d.get("inputs", ()))
    return UnifiedEvent(**d)
