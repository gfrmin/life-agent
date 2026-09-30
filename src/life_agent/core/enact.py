"""enact.py — the enactment of the decider's choice.

:func:`life_agent.core.decide.bayes_act` picks one :class:`~life_agent.core.decide.Option`
(abstain / a gather probe / ask / a candidate to respond with); this module lists the
options the ``/decide`` request opens and turns the winner into what the executor does.
It ranks nothing and picks nothing: no ``max``, ``min`` or ``sorted`` (drift-gated).

* **The gather options** are the request's unapplied voi transforms and grow actuators,
  each distinct probe once with the lowest price among its rows, listed in the order the
  probes' cheapest rows appear. Guard-kind transforms are never gather options.
* **respond → the candidate the option names, gather → the probe it names.**
* **ask → ask_clarify, abstain → abstain.**
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from life_agent.core import decide as DEC


def gather_options(payload: dict[str, Any]) -> list[tuple[str, float]]:
    """The unapplied gather options of a ``/decide`` request as ``(probe, cost)`` pairs, in
    the request's own price units (the executor has already converted them to utility). A
    probe's entry moves to the position of its cheapest row, so among equal prices the
    earlier row lists first."""
    applied = {str(a) for a in (payload.get("applied_probes") or [])}
    rows = [t for t in payload.get("transforms") or [] if t.get("kind") == "voi"]
    rows += list((payload.get("grow") or {}).get("actuators") or [])
    listed: dict[str, float] = {}
    for r in rows:
        probe, cost = str(r.get("probe") or ""), float(r.get("cost") or 0.0)
        if not probe or probe in applied:
            continue
        if probe in listed and cost >= listed[probe]:
            continue
        listed.pop(probe, None)
        listed[probe] = cost
    return list(listed.items())


def enact(option: DEC.Option, payload: dict[str, Any], credences: Sequence[float],
          p_none: float) -> dict[str, Any]:
    """The executor's view of the winning ``option``: ``effector`` plus ``value`` (the
    asserted candidate on a report) and ``probe`` (the gather to run)."""
    view: dict[str, Any] = {"credences": list(credences), "p_none": p_none,
                            "value": None, "probe": None}
    if option.action == "abstain":
        return {**view, "effector": "abstain"}
    if option.action == "ask":
        return {**view, "effector": "ask_clarify"}
    if option.action == "respond":
        candidates = [str(c) for c in payload.get("candidates") or []]
        if not isinstance(option.target, int) or len(candidates) != len(credences):
            raise ValueError("respond needs one credence per candidate")
        return {**view, "effector": "report", "value": candidates[option.target]}
    if option.action == "gather":
        if not isinstance(option.target, str):
            raise ValueError("gather was chosen with no gather option open")
        return {**view, "effector": "gather", "probe": option.target}
    raise ValueError(f"undeclared action {option.action!r} (declared: {list(DEC.ACTIONS)})")
