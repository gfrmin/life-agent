"""coarse.py — the enactment of the engine's coarse act.

The engine picks one of the world's four affordances (abstain / gather / ask / respond);
this module turns that act into what the executor does, given the ``/decide`` request it
was ranked over. It ranks nothing: every rule below is determined by the act and the
request alone.

* **respond → the MAP candidate.** A binary ``respond`` asserts; the world never says
  which candidate, so the host asserts the one with the most credence (candidate order
  breaks ties). This is value selection, not act ranking, and it is the one host argmax
  left on the path, disclosed as such in gfrmin/proplang#29 item 4.
* **gather → the cheapest unapplied gather option.** The options are the request's voi
  transforms and grow actuators, cheapest first (a stable sort, so menu order breaks
  ties). Guard-kind transforms are never gather options. The world only lets the engine
  choose gather while an option is open (:func:`gather_open`), so an empty list here is
  a contract error, not a fallback.
* **ask → ask_clarify, abstain → abstain.**
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from . import world as W


def gather_options(payload: dict[str, Any]) -> list[str]:
    """The unapplied gather options of a ``/decide`` request, cheapest first."""
    applied = {str(a) for a in (payload.get("applied_probes") or [])}
    rows = [t for t in payload.get("transforms") or [] if t.get("kind") == "voi"]
    rows += list((payload.get("grow") or {}).get("actuators") or [])
    ranked = sorted(rows, key=lambda r: float(r.get("cost") or 0.0))
    out: list[str] = []
    for r in ranked:
        probe = str(r.get("probe") or "")
        if probe and probe not in applied and probe not in out:
            out.append(probe)
    return out


def gather_cost(payload: dict[str, Any]) -> float:
    """The price of the gather that would be enacted (the cheapest open option), in the
    request's own units (the executor has already converted it to utility); 0 when none."""
    options = gather_options(payload)
    if not options:
        return 0.0
    rows = [t for t in payload.get("transforms") or [] if t.get("kind") == "voi"]
    rows += list((payload.get("grow") or {}).get("actuators") or [])
    return min(float(r.get("cost") or 0.0) for r in rows if str(r.get("probe")) == options[0])


def gather_open(payload: dict[str, Any]) -> bool:
    """Whether the world's gather row is open for this request."""
    return bool(gather_options(payload))


def enact(action: str, payload: dict[str, Any], credences: Sequence[float],
          p_none: float) -> dict[str, Any]:
    """The executor's view of the engine's ``action``: ``effector`` plus ``value`` (the
    asserted candidate on a report) and ``probe`` (the gather to run)."""
    view: dict[str, Any] = {"credences": list(credences), "p_none": p_none,
                            "value": None, "probe": None}
    if action == "abstain":
        return {**view, "effector": "abstain"}
    if action == "ask":
        return {**view, "effector": "ask_clarify"}
    if action == "respond":
        candidates = [str(c) for c in payload.get("candidates") or []]
        if not candidates or len(candidates) != len(credences):
            raise ValueError("respond needs one credence per candidate")
        leader = max(range(len(candidates)), key=lambda j: credences[j])
        return {**view, "effector": "report", "value": candidates[leader]}
    if action == "gather":
        options = gather_options(payload)
        if not options:
            raise ValueError("the engine chose gather with no gather option open")
        return {**view, "effector": "gather", "probe": options[0]}
    raise ValueError(f"undeclared engine action {action!r} "
                     f"(declared: {[a for a, _ in W.AFFORDANCES]})")
