"""Append-only event ledger for the trips faculty — the spine the timeline folds out of.

Mirrors tasks/events.py: append-only, corrections are new compensating entries, truth =
fold(events). The event vocabulary differs — a reservation is `observed` (by a source, at a
fidelity), an evolving booking is `superseded` (old identity -> new), a booking is
`cancelled`, and a field is manually `amended`. Within-identity dedup (Kayak + the same
flight's email) is fold-derived from competing `observed` events; cross-identity supersession
(a schedule change mints a new content key) is this explicit `superseded` edge.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

EventType = Literal["observed", "superseded", "cancelled", "amended"]

# Fidelity ranking — LOWER wins. Records resolve by (FIDELITY_RANK[fidelity], received_at).
FIDELITY_RANK: dict[str, int] = {
    "manual": 1,
    "email-kitinerary": 2,
    "kayak-api": 3,
    "kayak-ics": 4,
}

_SEP = "\x1f"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Event:
    """One immutable ledger entry concerning a single reservation ``identity``."""

    type: EventType
    identity: str
    tx_time: str
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
                _SEP.join([
                    self.type, self.identity, self.tx_time,
                    self.superseded_by or "", self.source_id or "", self.reason or "",
                    json.dumps(self.payload, sort_keys=True),
                ]).encode("utf-8")
            ).hexdigest()[:16]
            object.__setattr__(self, "event_id", digest)


def observed(
    identity: str,
    jsonld: dict[str, Any],
    *,
    fidelity: str,
    source_id: str,
    received_at: str,
    tx_time: str | None = None,
) -> Event:
    """A source asserted this reservation content, at a fidelity, received at a time."""
    return Event(
        type="observed", identity=identity, tx_time=tx_time or now_iso(),
        received_at=received_at, fidelity=fidelity, source_id=source_id, payload=jsonld,
    )


def superseded(old_identity: str, new_identity: str, *, tx_time: str | None = None) -> Event:
    """Link an evolving booking: the reschedule/re-issue minted a new content key."""
    return Event(type="superseded", identity=old_identity,
                 tx_time=tx_time or now_iso(), superseded_by=new_identity)


def cancelled(
    identity: str, reason: str, *,
    source_id: str | None = None, received_at: str | None = None, tx_time: str | None = None,
) -> Event:
    """Mark a reservation (and its supersession chain) cancelled — never a delete."""
    return Event(type="cancelled", identity=identity, tx_time=tx_time or now_iso(),
                 received_at=received_at, source_id=source_id, reason=reason)


def amended(identity: str, fields: dict[str, Any], *, tx_time: str | None = None) -> Event:
    """A manual field override (tier `manual` always wins in the fold)."""
    return Event(type="amended", identity=identity, tx_time=tx_time or now_iso(),
                 payload={"fields": fields})


def _to_json(e: Event) -> str:
    return json.dumps({
        "event_id": e.event_id, "type": e.type, "identity": e.identity,
        "tx_time": e.tx_time, "received_at": e.received_at, "fidelity": e.fidelity,
        "source_id": e.source_id, "superseded_by": e.superseded_by, "reason": e.reason,
        "payload": e.payload,
    }, ensure_ascii=False, sort_keys=True)


def _from_json(line: str) -> Event | None:
    try:
        d = json.loads(line)
        return Event(
            type=d["type"], identity=d["identity"], tx_time=d["tx_time"],
            received_at=d.get("received_at"), fidelity=d.get("fidelity"),
            source_id=d.get("source_id"), superseded_by=d.get("superseded_by"),
            reason=d.get("reason"), payload=d.get("payload", {}), event_id=d.get("event_id", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def append(ledger: Path, events: list[Event]) -> None:
    if not events:
        return
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for e in events:
            fh.write(_to_json(e) + "\n")


def load(ledger: Path) -> list[Event]:
    if not ledger.exists():
        return []
    out: list[Event] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        e = _from_json(line)
        if e is not None:
            out.append(e)
    return out
