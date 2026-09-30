"""Append-only event ledger for the trips faculty — the spine the timeline folds out of.

The ledger itself (append-only, corrections are new compensating entries, truth =
fold(events)) is core/events.py. The vocabulary here: a reservation is `observed` (by a
source, at a fidelity), an evolving booking is `superseded` (old identity -> new), a booking
is `cancelled`, and a field is manually `amended`. Within-identity dedup (Kayak + the same
flight's email) is fold-derived from competing `observed` events; cross-identity supersession
(a schedule change mints a new content key) is this explicit `superseded` edge.
"""
from __future__ import annotations

from typing import Any

from life_agent.core.events import Event, amended, append, load, now_iso, superseded

__all__ = ["FIDELITY_RANK", "Event", "amended", "append", "cancelled", "load", "now_iso",
           "observed", "superseded"]

# Fidelity ranking — LOWER wins. Records resolve by (FIDELITY_RANK[fidelity], received_at).
FIDELITY_RANK: dict[str, int] = {
    "manual": 1,
    "email-kitinerary": 2,
    "kayak-api": 3,
    "kayak-ics": 4,
}


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


def cancelled(
    identity: str, reason: str, *,
    source_id: str | None = None, received_at: str | None = None, tx_time: str | None = None,
) -> Event:
    """Mark a reservation (and its supersession chain) cancelled — never a delete."""
    return Event(type="cancelled", identity=identity, tx_time=tx_time or now_iso(),
                 received_at=received_at, source_id=source_id, reason=reason)
