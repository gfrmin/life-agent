"""truth = fold(events): resolve competing observations, supersession and cancellation.

Two dedup mechanisms meet here (see the plan's Reconciliations note):
 * same identity, many `observed` events -> the winner is highest fidelity, tie-broken by
   latest received_at. This is the free dedup content-keyed identity buys us.
 * different identities linked by `superseded` -> the old identity is retained but flagged.

The projection keeps ALL identities (superseded ancestors are retained, never deleted);
`superseded_by is None and not cancelled` is the predicate for a CURRENT reservation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from life_agent.trips.events import FIDELITY_RANK, Event


@dataclass(frozen=True)
class Reservation:
    identity: str
    jsonld: dict[str, Any]
    fidelity: str
    source_id: str
    received_at: str | None
    cancelled: bool = False
    superseded_by: str | None = None


def _better(a: Event, b: Event) -> Event:
    """The winning observation: lower fidelity rank wins; tie -> later received_at."""
    ra, rb = FIDELITY_RANK.get(a.fidelity or "", 99), FIDELITY_RANK.get(b.fidelity or "", 99)
    if ra != rb:
        return a if ra < rb else b
    return a if (a.received_at or "") >= (b.received_at or "") else b


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def fold(events: list[Event]) -> dict[str, Reservation]:
    winners: dict[str, Event] = {}
    for e in events:
        if e.type == "observed":
            winners[e.identity] = _better(winners[e.identity], e) if e.identity in winners else e

    reservations: dict[str, Reservation] = {
        ident: Reservation(
            identity=ident, jsonld=dict(w.payload), fidelity=w.fidelity or "",
            source_id=w.source_id or "", received_at=w.received_at,
        )
        for ident, w in winners.items()
    }

    for e in events:
        if e.type == "superseded" and e.identity in reservations:
            reservations[e.identity] = replace(reservations[e.identity], superseded_by=e.superseded_by)
        elif e.type == "cancelled" and e.identity in reservations:
            reservations[e.identity] = replace(reservations[e.identity], cancelled=True)
        elif e.type == "amended" and e.identity in reservations:
            merged = _deep_merge(reservations[e.identity].jsonld, e.payload.get("fields", {}))
            reservations[e.identity] = replace(reservations[e.identity], jsonld=merged)

    return reservations
