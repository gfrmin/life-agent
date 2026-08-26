"""coarse.py — the shadow worker's coarse-act mapping (measurement only).

The M3 live lane died at M5 (Q8, r15): the engine's coarse choice is never enacted.
What survives is :func:`map_action` — the PURE mapping from an engine affordance
(abstain / gather / ask / respond) onto what an enactment WOULD have been, given the
daemon's decision view. It runs BRIDGE-SIDE inside the shadow worker, so the one
``enact``-distance record can name both the engine's choice and what the host actually
did — the shadow's distance from the decision is the measurement (register §6.2).

**The mapping rules (measurement semantics, inherited from the retired lane):**

* **Agreement passes through.** When the engine's coarse act matches the daemon's
  effector's coarse class (:data:`~life_agent.membrane.world.REAL_TO_MEMBRANE`), the
  daemon's view stands unchanged.
* **respond → MAP.** The engine holds no per-candidate posterior, so an engine respond
  over a daemon withhold asserts the MAP candidate (argmax credence). No candidates ⇒
  degradation ``respond_no_value`` ⇒ abstain.
* **gather → cheapest unapplied voi transform** from the payload's own transform menu
  (menu order = cost order). Guards are never selected. Exhausted ⇒ degradation
  ``gather_exhausted``: the remainder {abstain, ask, respond} argmaxed at the engine's
  own p1 readout under the world's one utility source
  (:func:`~life_agent.membrane.world.eu_by_action`); missing p1/u_bar ⇒ ``no_p1`` ⇒
  abstain.
"""
from __future__ import annotations

from typing import Any

from . import world as W

# The engine's coarse vocabulary mapped to the effector the host enacts on an OVERRIDE
# (agreement keeps the daemon's finer effector instead — see map_action).
_ENACT_EFFECTOR = {"abstain": "abstain", "ask": "ask_clarify", "respond": "report"}


def _withhold(dec: dict[str, Any], effector: str) -> dict[str, Any]:
    """The daemon view rewritten to a withholding effector — posterior fields survive
    (the render footer stays honest); any asserted value does not."""
    return {**dec, "effector": effector, "value": None}


def _respond(payload: dict[str, Any], dec: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Engine respond over a daemon withhold: assert the host-MAP candidate (the
    transitional value selection — argmax credence, candidate order). Unenactable
    without a well-formed posterior: ``respond_no_value`` ⇒ abstain."""
    candidates = [str(c) for c in (payload.get("candidates") or [])]
    credences = dec.get("credences") or []
    if not candidates or len(candidates) != len(credences):
        return _withhold(dec, "abstain"), "respond_no_value"
    leader = max(range(len(candidates)), key=lambda j: credences[j])
    return {**dec, "effector": "report", "value": candidates[leader]}, None


def _gather(payload: dict[str, Any], dec: dict[str, Any],
            readouts: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Engine gather over a daemon terminal: enact the cheapest unapplied voi transform;
    exhausted ⇒ restricted argmax at the engine's own p1 (module docstring)."""
    applied = {str(a) for a in (payload.get("applied_probes") or [])}
    for t in payload.get("transforms") or []:
        probe = str(t.get("probe") or "")
        if t.get("kind") == "voi" and probe and probe not in applied:
            return {**dec, "effector": "gather", "probe": probe}, None
    p1 = readouts.get("p1")
    u_bar = payload.get("u_bar")
    if not isinstance(p1, (int, float)) or isinstance(p1, bool) or not isinstance(u_bar, dict):
        return _withhold(dec, "abstain"), "no_p1"
    eus = W.eu_by_action(u_bar, float(p1))
    fallback = "abstain"
    for name, _v in W.AFFORDANCES:  # grid order = the wire's own first-listed tie rule
        if name != "gather" and eus[name] > eus[fallback]:
            fallback = name
    if fallback == "respond":
        view, reason = _respond(payload, dec)
        return view, "gather_exhausted" if reason is None else reason
    return _withhold(dec, _ENACT_EFFECTOR[fallback]), "gather_exhausted"


def map_action(payload: dict[str, Any], dec: dict[str, Any], action: str,
               readouts: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Map the engine's coarse ``action`` onto an enactable rewrite of the daemon view
    ``dec``, given the ``/decide`` request ``payload`` it was computed from. Returns
    ``(view, degraded)`` — ``degraded`` names the transitional-rule degradation when the
    engine's choice could not be enacted as-is (``respond_no_value`` /
    ``gather_exhausted`` / ``no_p1``), else ``None``."""
    if action == W.REAL_TO_MEMBRANE.get(str(dec.get("effector"))):
        return dec, None  # agreement — the daemon's finer selection stands
    if action == "abstain":
        return _withhold(dec, "abstain"), None
    if action == "ask":
        return _withhold(dec, "ask_clarify"), None
    if action == "respond":
        return _respond(payload, dec)
    assert action == "gather", f"undeclared engine action {action!r}"
    return _gather(payload, dec, readouts)

