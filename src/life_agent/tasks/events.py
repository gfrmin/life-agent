"""Append-only event ledger for the act layer — the spine the task list folds out of.

The authoritative, immutable record of what the agent has **asserted** (a grounded
action item, filed as a task) and how each assertion was later **disposed** or
**superseded**. It is a *ledger* in the accounting sense — append-only, corrections
are new compensating entries, you never erase — so ``truth = fold(events)`` is a
pure, replayable function of the log, not a mutable side-store you can lose.

Two properties earn their keep here (see ``reconciliation-as-transformation`` notes):

- **Assertion identity** keys an assertion on its *content + grounding*, deliberately
  NOT on the model/prompt/schema that produced it. That is the pkm *cache key*'s job
  (byte-reproducibility, so it *should* change on a prompt bump); identity needs the
  opposite — referential stability across re-derivation — so the same claim re-derived
  later dedups, and a positional index never enters into it.
- **Immutability ≠ determinism.** A stochastic transform has no deterministic value,
  but the instant it runs it produces an immutable *fact* stamped with ``tx_time``.
  We replay the recorded draw, never re-roll it, so the fold stays deterministic even
  though the draw was not. ``tx_time`` is the only clock that matters (no time machines).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Any

from life_agent.core.events import SEP as _SEP
from life_agent.core.events import Event, amended, append, load, now_iso, superseded

__all__ = ["Event", "OpenAssertion", "amended", "append", "asserted", "assertion_identity",
           "disposed", "fold", "known_identities", "load", "new_identity", "now_iso",
           "superseded"]

_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Whitespace-normalised (case preserved), matching pkm's grounding contract."""
    return _WS.sub(" ", text).strip()


def assertion_identity(claim_type: str, grounding_span: str, claim_content: str) -> str:
    """Stable identity for a derived assertion: content + grounding, NOT provenance.

    Excludes model/prompt/schema. Two extractions yielding the same claim text from
    the same span share an identity and dedup — even across a prompt/model bump that
    leaves the text unchanged, and regardless of position within the email. A reworded
    claim is a *different* identity that the correlator may later link with a
    ``superseded`` event; it never silently collides with the old one.
    """
    parts = (_normalize(claim_type), _normalize(grounding_span), _normalize(claim_content))
    return hashlib.sha256(_SEP.join(parts).encode("utf-8")).hexdigest()


def new_identity() -> str:
    """A unique identity for a *human-originated* assertion.

    Unlike ``assertion_identity`` (content-addressed, so a re-derivation dedups), a human
    typing the same task twice *means* two tasks — so each human command gets a fresh,
    unique id. The randomness happens once, at command time (the draw); it is then recorded
    in the event and replayed deterministically.
    """
    return uuid.uuid4().hex


def asserted(
    identity: str,
    payload: dict[str, Any],
    *,
    valid_time: str | None = None,
    tx_time: str | None = None,
) -> Event:
    """Open an assertion: a grounded item the agent has filed as a task."""
    return Event(
        type="asserted",
        identity=identity,
        tx_time=tx_time or now_iso(),
        valid_time=valid_time,
        payload=payload,
    )


def disposed(identity: str, reason: str, *, tx_time: str | None = None) -> Event:
    """Close an assertion the human disposed of (a compensating entry, never a delete)."""
    return Event(type="disposed", identity=identity, tx_time=tx_time or now_iso(), reason=reason)


@dataclass(frozen=True)
class OpenAssertion:
    """A currently-open assertion in the projection (what ``fold`` yields)."""

    identity: str
    payload: dict[str, Any]
    asserted_at: str
    valid_time: str | None


def fold(events: list[Event]) -> dict[str, OpenAssertion]:
    """Replay the ledger → the currently-open assertions (the task projection).

    ``asserted`` opens an identity; ``disposed`` and ``superseded`` close it for good.
    *Close always wins* (a disposed identity never reopens, even if re-asserted later —
    don't resurrect what the human cleared), which also makes the fold order-independent
    and therefore stable across replay.
    """
    closed: set[str] = {e.identity for e in events if e.type in ("disposed", "superseded")}
    open_: dict[str, OpenAssertion] = {}
    for e in events:
        if e.type == "asserted" and e.identity not in closed:
            open_[e.identity] = OpenAssertion(
                identity=e.identity,
                payload=e.payload,
                asserted_at=e.tx_time,
                valid_time=e.valid_time,
            )
    return open_


def known_identities(events: list[Event]) -> set[str]:
    """Every assertion identity the ledger has ever recorded — the set that suppresses
    re-filing. Each is either still *open* (already filed) or *closed* (handled/cleared);
    neither is *fresh*. Distinct from ``fold`` (the open subset) so disposal never
    resurrects: a cleared identity stays known, hence is never re-filed.
    """
    return {e.identity for e in events}
