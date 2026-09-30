"""The append-only event ledger the GTD task list and the trips timeline both fold out of.

One immutable :class:`Event` per entry, appended through :mod:`life_agent.core.jsonl_log`;
corrections are new compensating entries, never edits, so ``truth = fold(events)`` is a pure,
replayable function of the log. The vocabularies differ by faculty — ``asserted`` /
``disposed`` for tasks (:mod:`life_agent.tasks.events`), ``observed`` / ``cancelled`` for trips
(:mod:`life_agent.trips.events`) — and those modules hold the constructors and the fold
that are theirs; ``superseded`` and ``amended`` mean the same in both and live here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from life_agent.core import jsonl_log

EventType = Literal["asserted", "disposed", "observed", "cancelled", "superseded", "amended"]

SEP = "\x1f"  # unit separator — never appears in normalised text


def now_iso() -> str:
    """Wall-clock stamp for an event (``tx_time``), local and to the second."""
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Event:
    """One immutable ledger entry concerning a single ``identity`` (a task assertion or a
    reservation). The optional fields belong to one faculty each: ``valid_time`` to tasks;
    ``received_at``, ``fidelity`` and ``source_id`` to trips."""

    type: EventType
    identity: str
    tx_time: str
    valid_time: str | None = None
    received_at: str | None = None
    fidelity: str | None = None
    source_id: str | None = None
    superseded_by: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            digest = hashlib.sha256(
                SEP.join([
                    self.type, self.identity, self.tx_time,
                    self.superseded_by or "", self.source_id or "", self.reason or "",
                    json.dumps(self.payload, sort_keys=True),
                ]).encode("utf-8")
            ).hexdigest()[:16]
            object.__setattr__(self, "event_id", digest)


def superseded(old_identity: str, new_identity: str, *, tx_time: str | None = None) -> Event:
    """Close ``old_identity`` because a newer one replaces it (the correlator's edge)."""
    return Event(type="superseded", identity=old_identity,
                 tx_time=tx_time or now_iso(), superseded_by=new_identity)


def amended(identity: str, fields: dict[str, Any], *, tx_time: str | None = None) -> Event:
    """Amend an open identity's mutable attributes (a move, a reschedule, a manual override).
    The amendment does not close it; the projection applies ``fields`` over the current row."""
    return Event(type="amended", identity=identity, tx_time=tx_time or now_iso(),
                 payload={"fields": fields})


def _to_json(e: Event) -> str:
    return json.dumps(asdict(e), ensure_ascii=False, sort_keys=True)


def _from_json(line: str) -> Event | None:
    try:
        d = json.loads(line)
        return Event(
            type=d["type"], identity=d["identity"], tx_time=d["tx_time"],
            valid_time=d.get("valid_time"), received_at=d.get("received_at"),
            fidelity=d.get("fidelity"), source_id=d.get("source_id"),
            superseded_by=d.get("superseded_by"), reason=d.get("reason"),
            payload=d.get("payload", {}), event_id=d.get("event_id", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def append(ledger: Path, events: list[Event]) -> None:
    """Append events to the ledger, durably (creates the directory on first use)."""
    for e in events:
        jsonl_log.append_line(ledger, _to_json(e))


def load(ledger: Path) -> list[Event]:
    """Read the whole ledger in order (empty if it doesn't exist); skips garbage lines."""
    return [e for e in map(_from_json, jsonl_log.read_lines(ledger)) if e is not None]
