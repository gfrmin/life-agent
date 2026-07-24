"""Mailbox-scale ingest: notmuch selection -> forward resolution -> extract -> observe.

The tier-2 (email-kitinerary) upgrade path. Selection is a notmuch query (config, never a
literal). A selected forward is resolved to its original and extraction runs on whichever of
{original, forward} yields more — the original is better evidence, so it wins a tie. Every
reservation is observed idempotently (observe dedups on (identity, source_id)), so re-running
a broadened query costs nothing. A failure of the top-level SELECTION search raises (a bad
query / broken index invalidates the whole run); per-message notmuch or parse failures are
logged, skipped, and counted, and a per-message forward-resolution failure degrades to the
forward — one bad mail never aborts the batch. One extraction seam, one write path.
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any

from life_agent.core import config
from life_agent.trips import commands, forwards
from life_agent.trips import notmuch as _notmuch
from life_agent.trips.extract import extract as _extract

_log = logging.getLogger(__name__)


class IngestConfigError(RuntimeError):
    """The ingest query is not configured (data-sources.yaml:trips.ingest.query)."""


@dataclass
class Stats:
    selected: int = 0
    forwards_resolved: int = 0
    messages_with_yield: int = 0
    reservations: int = 0
    errors: int = 0


def configured_query() -> str:
    """The owner's booking-signal query from data-sources.yaml. Raises when unset — never a
    silent empty run."""
    ds = config.data_sources()
    trips = ds.get("trips") if isinstance(ds, dict) else None
    ingest = trips.get("ingest") if isinstance(trips, dict) else None
    query = ingest.get("query") if isinstance(ingest, dict) else None
    if not isinstance(query, str) or not query.strip():
        raise IngestConfigError(
            f"no trips.ingest.query in {config.DATA_SOURCES}; set it or pass --query"
        )
    return query


def _parse(raw: bytes) -> EmailMessage:
    msg = message_from_bytes(raw, policy=policy.default)
    assert isinstance(msg, EmailMessage)
    return msg


def _context_date(msg: EmailMessage) -> datetime:
    raw = msg.get("Date")
    if raw:
        try:
            return parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            pass
    return datetime.now()


def _message_id(msg: EmailMessage, fallback: str) -> str:
    mid = (msg.get("Message-ID") or "").strip().strip("<>").strip()
    return mid or fallback


def ingest_query(
    query: str,
    *,
    nm: Any = _notmuch,
    extract_fn: Callable[[bytes, datetime], list[dict[str, Any]]] = _extract,
    observe_fn: Callable[..., str] = commands.observe,
    limit: int | None = None,
    dry_run: bool = False,
) -> Stats:
    """Ingest every reservation selected by ``query``. See module docstring for the contract."""
    stats = Stats()
    ids = nm.search(query)          # NotmuchError propagates: a bad query invalidates the run
    if limit is not None:
        ids = ids[:limit]
    stats.selected = len(ids)

    for msgid in ids:
        try:
            fwd_raw = nm.show_raw(msgid)
            fwd_msg = _parse(fwd_raw)
            candidates: list[tuple[bytes, EmailMessage]] = [(fwd_raw, fwd_msg)]

            # Forward resolution is BEST-EFFORT: a per-message lookup failure (e.g. a
            # malformed subject query, or a broken index mid-scan) must NOT skip an otherwise
            # extractable message, and must never abort the batch.
            try:
                original_id = forwards.resolve_original(dict(fwd_msg.items()), nm.search)
            except _notmuch.NotmuchError:
                original_id = None
            if original_id and original_id != msgid:
                try:
                    orig_raw = nm.show_raw(original_id)
                    candidates.insert(0, (orig_raw, _parse(orig_raw)))  # original first (tie->orig)
                    stats.forwards_resolved += 1
                except _notmuch.NotmuchError:
                    pass                # original unfetchable (e.g. deleted) -> use the forward

            best: tuple[bytes, EmailMessage, list[dict[str, Any]]] = (fwd_raw, fwd_msg, [])
            for raw, msg in candidates:
                found = extract_fn(raw, _context_date(msg))
                if len(found) > len(best[2]):
                    best = (raw, msg, found)
        except Exception as exc:        # one malformed/unfetchable message never aborts the batch
            _log.warning("trips ingest: skipped %s (%s)", msgid, type(exc).__name__)
            stats.errors += 1
            continue

        best_raw, best_msg, best_yield = best
        if not best_yield:
            continue
        stats.messages_with_yield += 1
        if dry_run:
            stats.reservations += len(best_yield)
            continue

        message_id = _message_id(best_msg, msgid)
        sha = hashlib.sha256(best_raw).hexdigest()
        received = _context_date(best_msg).isoformat()
        for jsonld in best_yield:
            observe_fn(
                jsonld, fidelity="email-kitinerary", source_id=f"mail:{message_id}",
                received_at=received,
                source_meta={"message_id": message_id, "sha256": sha, "kind": "email"},
            )
            stats.reservations += 1
    return stats
