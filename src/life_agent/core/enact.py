"""enact.py — the enactment of the decider's act.

:func:`life_agent.core.decide.bayes_act` picks one of the four actions (abstain / gather
/ ask / respond) and, when it picks gather, :func:`life_agent.core.decide.best_gather` has
already picked which option; this module turns that into what the executor does. It ranks
nothing: every rule below is determined by the act and the request alone.

* **respond → the MAP candidate.** ``respond`` asserts the candidate with the most
  credence (candidate order breaks ties): with ``u_correct`` equal across candidates this IS
  the Bayes act's value, not a second ranking.
* **gather → the option the act chose.** :func:`gather_options` reads the menu the request
  carries — its voi transforms and grow actuators, each with its price, in menu order and
  minus the ones already applied (guard-kind transforms are never gather options). The act
  ranks gather only while the menu is non-empty (:func:`gather_open`), so an empty menu
  here is a contract error, not a fallback.
* **ask → ask_clarify, abstain → abstain.**
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from life_agent.core import decide as DEC


def gather_options(payload: dict[str, Any]) -> list[tuple[str, float]]:
    """The unapplied gather options of a ``/decide`` request as ``(probe, price)``, in menu
    order. The price is the request's own (the executor has already converted it to utility
    units); an option offered twice is priced at its cheapest row."""
    applied = {str(a) for a in (payload.get("applied_probes") or [])}
    rows = [t for t in payload.get("transforms") or [] if t.get("kind") == "voi"]
    rows += list((payload.get("grow") or {}).get("actuators") or [])
    out: dict[str, float] = {}
    for r in rows:
        probe = str(r.get("probe") or "")
        if not probe or probe in applied:
            continue
        price = float(r.get("cost") or 0.0)
        out[probe] = min(price, out[probe]) if probe in out else price
    return list(out.items())


def gather_open(payload: dict[str, Any]) -> bool:
    """Whether the world's gather row is open for this request."""
    return bool(gather_options(payload))


def enact(action: str, payload: dict[str, Any], credences: Sequence[float],
          p_none: float, *, probe: str | None = None) -> dict[str, Any]:
    """The executor's view of the decider's ``action``: ``effector`` plus ``value`` (the
    asserted candidate on a report) and ``probe`` (the gather the act chose)."""
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
        if probe is None:
            raise ValueError("gather was chosen with no gather option open")
        return {**view, "effector": "gather", "probe": probe}
    raise ValueError(f"undeclared action {action!r} (declared: {list(DEC.ACTIONS)})")
