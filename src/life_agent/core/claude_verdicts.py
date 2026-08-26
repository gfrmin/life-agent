"""The Claude verdict channel — deliberative verdicts issued on the owner's behalf.

Owner ruling (2026-07-22): Claude Code — the in-session, deliberative agent, never a
one-shot API call — may issue verdicts on answers on the owner's behalf, and the owner may
overrule any of them. Answer quality is multidimensional and objective; conversion to a
single score is DEFERRED. This module is that ruling as code:

**The record stores dimensions raw.** ``dimensions`` is a declared closed vocabulary of
independent objective bits — no combined scalar exists anywhere in the record. The engine
projection :func:`y` reads ONLY the ``correct`` dimension ("asserting the decision's
leader candidate now would have been correct" — exactly the fact the membrane's ``said@1``
utility form prices). That is a measured bit, not a scalarization: the deferred
single-score question stays open.

**A third reliability class** (proplang OB-12's register): denser than the owner's
verdicts, more authoritative than the extraction ticks. It feeds the ENGINE's verdict
evidence only (``membrane.shadow.boot_snapshot`` merges it under owner precedence) and
NEVER the utility posterior — P(U) is the owner's revealed preference, and a Claude
verdict is a truth measurement, not a preference. The isolation is by construction:
``core.reactions.load_reactions`` reads a different file and is untouched.

**Overrule is by source, not file order — and it belongs to an owner VERDICT, not a
reaction row.** An owner reaction on the same ``decision_id`` that decodes through
``verdict_y`` supersedes every Claude verdict on it, regardless of which came later (the
merge lives in ``boot_snapshot``); an unrouted reaction (e.g. ``good`` on a ``hedge``)
contributes no owner verdict and blocks nothing. Among Claude verdicts, the latest per decision wins
(:func:`latest_by_decision` — file order is replay order, the ``core.reactions``
convention).

**Every verdict must be deliberated, never batch-derived.** The issuer is this agent
reading the decision's actual candidate against the corpus; mechanically projecting a
grader's output through this log would silently re-create the extraction channel at
owner-verdict authority. ``evidence`` names what the deliberation read (KB-side paths —
the log lives under ``$LIFE_AGENT_KB``, never in the public tree).
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType
from typing import Any

from life_agent.core import jsonl_log

FORMAT_VERSION = 1

ISSUER = "claude-code"

# The closed dimension vocabulary (grow by edit — an undeclared dimension is a loud
# construction error, the reactions.py convention). Each is an independent objective bit:
#   correct  — asserting the decision's leader candidate now would have been correct
#   complete — the candidate covers every gold component the question asks for
#   grounded — the candidate is supported by the cited/retrieved sources
# ``correct`` is required (it is the engine projection); the others are optional.
DIMENSIONS: frozenset[str] = frozenset({"correct", "complete", "grounded"})
_REQUIRED: frozenset[str] = frozenset({"correct"})


@dataclass(frozen=True)
class ClaudeVerdictEvent:
    """One deliberative verdict on one logged decision (format_version 1).

    ``dimensions`` maps declared dimension names to bits (0/1); ``correct`` is required.
    ``evidence`` names what the deliberation read (source paths/quotes — KB-side).
    ``note`` is free text FROM the agent (the owner's prose stays the loop's one
    expensive resource; this channel spends the agent's, which is cheap)."""

    tx_time: str
    question_id: str
    decision_id: str
    dimensions: Mapping[str, int]
    evidence: tuple[str, ...] = ()
    note: str = ""
    issuer: str = ISSUER
    format_version: int = FORMAT_VERSION

    def __post_init__(self) -> None:
        dims = dict(self.dimensions)
        unknown = set(dims) - DIMENSIONS
        if unknown:
            raise ValueError(
                f"undeclared dimension(s) {sorted(unknown)} "
                f"(declared: {sorted(DIMENSIONS)})")
        missing = _REQUIRED - set(dims)
        if missing:
            raise ValueError(f"missing required dimension(s) {sorted(missing)}")
        for name, value in dims.items():
            if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
                raise ValueError(f"dimension {name!r} must be the bit 0 or 1, got {value!r}")
        # freeze: the event is a value; a caller's later dict mutation must not leak in
        object.__setattr__(self, "dimensions", MappingProxyType(dims))
        object.__setattr__(self, "evidence", tuple(self.evidence))


_FIELDS: frozenset[str] = frozenset(f.name for f in fields(ClaudeVerdictEvent))


def y(event: ClaudeVerdictEvent) -> int:
    """The engine projection: y = the ``correct`` bit ("asserting now would have been
    correct"), and nothing else — completeness/grounding are recorded, not priced, until
    the deferred scalarization is decided. A branch of THE verdict→evidence projection
    (D-15 — the one declaration lives at ``core.reactions.VERDICT_Y``); admitted under
    owner ≻ Claude precedence at the ``membrane.shadow.boot_snapshot`` merge."""
    return event.dimensions["correct"]


def _to_line(event: ClaudeVerdictEvent) -> str:
    row: dict[str, Any] = {
        "tx_time": event.tx_time, "question_id": event.question_id,
        "decision_id": event.decision_id, "dimensions": dict(event.dimensions),
        "evidence": list(event.evidence), "note": event.note,
        "issuer": event.issuer, "format_version": event.format_version,
    }
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def from_line(line: str) -> ClaudeVerdictEvent:
    # Drop keys no longer in the schema — the append-only log must replay across a field
    # retirement rather than crash on an old row (the reactions.py convention).
    raw = {k: v for k, v in json.loads(line).items() if k in _FIELDS}
    if "evidence" in raw:
        raw["evidence"] = tuple(str(x) for x in raw["evidence"])
    return ClaudeVerdictEvent(**raw)


def append(path: Path, event: ClaudeVerdictEvent) -> None:
    """Append one verdict line, durably (the shared append-only mechanics), then mirror it onto
    the unified stream (design §8 C5; legacy-append-first, never raises)."""
    jsonl_log.append_line(path, _to_line(event))
    from life_agent.ledger import mirror as _mirror  # C5 dual-write: after the legacy append
    _mirror.after_legacy_append("calibration.claude_verdicts", path)


def read(path: Path) -> list[ClaudeVerdictEvent]:
    """Every verdict in file order — the canonical replay order. Structurally-malformed
    lines raise (the caller decides fail-open vs loud, as with ``reactions.read``)."""
    return [from_line(line) for line in jsonl_log.read_lines(path)]


def latest_by_decision(
    events: list[ClaudeVerdictEvent],
) -> dict[str, ClaudeVerdictEvent]:
    """Supersession: the latest Claude verdict per ``decision_id`` (file order is replay
    order), so one decision contributes one evidence tick."""
    latest: dict[str, ClaudeVerdictEvent] = {}
    for e in events:
        latest[e.decision_id] = e
    return latest
