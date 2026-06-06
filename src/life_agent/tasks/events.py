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
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

EventType = Literal["asserted", "disposed", "superseded"]

_WS = re.compile(r"\s+")
_SEP = "\x1f"  # unit separator — never appears in normalised text


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


def now_iso() -> str:
    """Wall-clock stamp for an event (``tx_time``)."""
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Event:
    """One immutable ledger entry concerning a single assertion ``identity``."""

    type: EventType
    identity: str
    tx_time: str
    valid_time: str | None = None
    reason: str | None = None
    superseded_by: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            digest = hashlib.sha256(
                _SEP.join(
                    [
                        self.type, self.identity, self.tx_time,
                        self.reason or "", self.superseded_by or "",
                    ]
                ).encode("utf-8")
            ).hexdigest()[:16]
            object.__setattr__(self, "event_id", digest)


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


def superseded(old_identity: str, new_identity: str, *, tx_time: str | None = None) -> Event:
    """Close ``old_identity`` because a newer assertion replaces it (the correlator's edge)."""
    return Event(
        type="superseded",
        identity=old_identity,
        tx_time=tx_time or now_iso(),
        superseded_by=new_identity,
    )


@dataclass(frozen=True)
class OpenAssertion:
    """A currently-open assertion in the projection (what ``fold`` yields)."""

    identity: str
    payload: dict[str, Any]
    asserted_at: str
    valid_time: str | None


def _to_json(e: Event) -> str:
    return json.dumps(
        {
            "event_id": e.event_id,
            "type": e.type,
            "identity": e.identity,
            "tx_time": e.tx_time,
            "valid_time": e.valid_time,
            "reason": e.reason,
            "superseded_by": e.superseded_by,
            "payload": e.payload,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _from_json(line: str) -> Event | None:
    try:
        d = json.loads(line)
        return Event(
            type=d["type"],
            identity=d["identity"],
            tx_time=d["tx_time"],
            valid_time=d.get("valid_time"),
            reason=d.get("reason"),
            superseded_by=d.get("superseded_by"),
            payload=d.get("payload", {}),
            event_id=d.get("event_id", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def append(ledger: Path, events: list[Event]) -> None:
    """Append events to the ledger (creates the directory on first use)."""
    if not events:
        return
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for e in events:
            fh.write(_to_json(e) + "\n")


def load(ledger: Path) -> list[Event]:
    """Read the whole ledger in order (empty if it doesn't exist); skips garbage lines."""
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
