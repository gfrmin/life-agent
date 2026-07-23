# src/life_agent/trips/commands.py
"""Trips commands — the event-sourced write layer.

Each command appends event(s) to the JSONL ledger (truth) then rebuilds the SQLite
projection from the full ledger (the fold is global, so a targeted apply would be wrong).
`observe` is idempotent on (identity, source_id): re-observing the same content from the
same source is a no-op, so re-running an import or re-ingesting a message never double-files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from life_agent.core.config import TRIPS_LEDGER
from life_agent.trips import events as ev
from life_agent.trips import store
from life_agent.trips.identity import reservation_identity

LEDGER_PATH: Path = TRIPS_LEDGER


def _rebuild() -> None:
    with store.get_db() as conn:
        store.rebuild(conn, ev.load(LEDGER_PATH))


def _already_observed(identity: str, source_id: str) -> bool:
    return any(
        e.type == "observed" and e.identity == identity and e.source_id == source_id
        for e in ev.load(LEDGER_PATH)
    )


def observe(
    jsonld: dict[str, Any], *, fidelity: str, source_id: str, received_at: str,
    source_meta: dict[str, Any] | None = None,
) -> str:
    """Record that `source_id` observed this reservation at `fidelity`. Returns the identity."""
    identity = reservation_identity(jsonld)
    if _already_observed(identity, source_id):
        return identity  # idempotent
    ev.append(LEDGER_PATH, [ev.observed(identity, jsonld, fidelity=fidelity,
                                        source_id=source_id, received_at=received_at)])
    meta = source_meta or {}
    with store.get_db() as conn:
        store.upsert_source(conn, source_id, message_id=meta.get("message_id"),
                            path=meta.get("path"), sha256=meta.get("sha256"),
                            received_at=received_at, fidelity=fidelity,
                            kind=meta.get("kind", ""))
    _rebuild()
    return identity


def cancel(identity: str, reason: str, *, source_id: str | None = None,
           received_at: str | None = None) -> str:
    ev.append(LEDGER_PATH, [ev.cancelled(identity, reason, source_id=source_id,
                                         received_at=received_at)])
    _rebuild()
    return identity


def amend(identity: str, fields: dict[str, Any]) -> str:
    ev.append(LEDGER_PATH, [ev.amended(identity, fields)])
    _rebuild()
    return identity


def supersede(old_identity: str, new_identity: str) -> str:
    ev.append(LEDGER_PATH, [ev.superseded(old_identity, new_identity)])
    _rebuild()
    return new_identity
