"""enact.py — the enactment of the decider's choice.

:func:`life_agent.core.decide.bayes_act` picks one :class:`~life_agent.core.decide.Option`
(abstain / a gather probe / ask / a candidate to respond with); this module lists the
options the ``/decide`` request opens and turns the winner into what the executor does.
It ranks nothing and picks nothing: no ``max``, ``min`` or ``sorted`` (drift-gated).

* **The gather options** are the request's unapplied voi transforms and grow actuators,
  each distinct probe once with the lowest price among its rows, listed in the order the
  probes' cheapest rows appear. Guard-kind transforms are never gather options.
* **The cite options** are the request's documents: each ``group`` holding an observation
  flagged ``document``, with the candidate indices its observations report — integers only.
* **respond → the candidate the option names, gather → the probe it names, cite → the
  document group it names** (``effector`` ``cite``, no value).
* **ask → ask_clarify, abstain → abstain.**
* **At the route stage** (:func:`enact_route`): attempt → the ``attempt`` effector (the
  executor runs a pass), abstain → ``abstain`` (the executor builds the declined view).
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


def document_groups(observations: Sequence[dict[str, Any]]) -> list[tuple[int, list[int]]]:
    """The documents among a ``/decide`` request's observations as ``(group, candidate
    indices)`` pairs: the groups in first-seen order that hold at least one observation
    flagged ``document`` (the executor's statement that it stands behind a retrieved hit;
    an observation without the flag is not one), each with the distinct candidate indices
    its observations report, each once, in first-seen order."""
    reported: dict[int, dict[int, None]] = {}
    documents: set[int] = set()
    for o in observations:
        g = int(o["group"])
        reported.setdefault(g, {})[int(o["reports"])] = None
        if o.get("document"):
            documents.add(g)
    return [(g, list(js)) for g, js in reported.items() if g in documents]


def enact(option: DEC.Option, payload: dict[str, Any], credences: Sequence[float],
          p_none: float) -> dict[str, Any]:
    """The executor's view of the winning ``option``: ``effector`` plus ``value`` (the
    asserted candidate on a report), ``probe`` (the gather to run), and ``group`` with
    ``p_group`` (the document a cite names, and the credence that it holds the answer)."""
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
    if option.action == "cite":
        if not isinstance(option.target, int):
            raise ValueError("cite needs the document group it names")
        reported = dict(document_groups(payload.get("observations") or []))
        return {**view, "effector": "cite", "group": option.target,
                "p_group": DEC.p_document(credences, reported.get(option.target, ()))}
    if option.action == "gather":
        if not isinstance(option.target, str):
            raise ValueError("gather was chosen with no gather option open")
        return {**view, "effector": "gather", "probe": option.target}
    raise ValueError(f"undeclared action {option.action!r} (declared: {list(DEC.ACTIONS)})")


def enact_route(option: DEC.Option) -> dict[str, Any]:
    """The executor's view of the route stage's winning ``option``: ``effector`` is
    ``attempt`` (run the pass) or ``abstain`` (decline the question)."""
    if option.action not in DEC.ROUTE_ACTIONS:
        raise ValueError(f"undeclared route action {option.action!r} "
                         f"(declared: {list(DEC.ROUTE_ACTIONS)})")
    return {"effector": option.action, "credences": [], "p_none": None,
            "value": None, "probe": None}
