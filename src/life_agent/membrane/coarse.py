"""coarse.py — M3: the coarse menu live (gold-standard roadmap, 2026-07-19).

The proplang engine chooses among this world's four affordances — abstain, gather, ask,
respond — ON the answer path, flag-gated (``LIFE_AGENT_MEMBRANE_LIVE=1``; absence is the
default and leaves every caller byte-for-byte on today's behaviour). The daemon still
computes the posterior each tick; the engine's coarse choice is mapped onto an ENACTABLE
rewrite of the daemon's own decision view, committed through the one act seam
(:mod:`life_agent.core.seam` — ``DaemonDecide.live`` is this module's closure).

Two surfaces:

* :func:`map_action` — the pure mapping. Runs BRIDGE-SIDE (inside the shadow worker,
  :meth:`life_agent.membrane.shadow.MembraneShadow.decide_live`), so the one ``enact``
  record can name both the engine's choice and what the host actually enacted.
* :func:`live_decide` — the host-side consult closure: one ``POST /decide-live``
  round-trip on its own bounded transport; ANY failure (down bridge, dead engine,
  malformed reply) is the DECLARED :data:`~life_agent.core.seam.GATE_ENGINE_DOWN`
  abstain, never a silent host guess.

**The transitional rules (every one named, each with its M5 exit):**

* **Agreement passes through.** When the engine's coarse act matches the daemon's
  effector's coarse class (:data:`~life_agent.membrane.world.REAL_TO_MEMBRANE`), the
  daemon's view stands unchanged — fine-grained selection (report vs hedge, which
  probe) is the daemon's until M5's value-indexed acts land.
* **respond → host MAP.** The engine holds no per-candidate posterior (E1 is the
  categorical-outcome extension, not yet built), so an engine respond over a daemon
  withhold asserts the MAP candidate (argmax credence). No candidates ⇒ degradation
  ``respond_no_value`` ⇒ abstain.
* **gather → cheapest unapplied voi transform.** The engine's gather is coarse; the
  fine actuator is chosen transitionally as the first unapplied ``kind: "voi"`` row of
  the payload's own transform menu (menu order = cost order — the k=0 walk's own
  precedent). Guards are never selected (they are trigger-conditional and
  daemon-priced). Exhausted ⇒ degradation ``gather_exhausted``: the enactable remainder
  {abstain, ask, respond} is argmaxed at the engine's OWN p1 readout under the world's
  one utility source (:func:`~life_agent.membrane.world.eu_by_action` over the
  payload's u_bar) — the engine's world, restricted to what the host can still do; a
  missing p1/u_bar ⇒ ``no_p1`` ⇒ abstain. E3 (engine-held stop-rule) is this rule's
  exit.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from life_agent.core import seam as SEAM

from . import world as W

# The live consult's own transport bound. This IS on the answer path (deliberately — the
# engine is the decider now), but a wedged bridge must cost a bounded wait, never a
# real-leg 300s timeout: past this, the consult fails into the declared engine-down
# abstain. Comfortably above the shadow's own bounded wait (shadow._LIVE_WAIT_S), so the
# bridge's honest "down" reply is what times out last, not first.
LIVE_TIMEOUT_S = 20.0

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


# --- the host-side consult closure (the seam's DaemonDecide.live) ------------------------


def _live_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """The consult's own transport — the same urllib idiom as every poster in this
    codebase, bounded to :data:`LIVE_TIMEOUT_S`. Never a real-leg 300s poster."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=LIVE_TIMEOUT_S) as r:
        out: dict[str, Any] | None = json.loads(r.read())
        return out


def live_decide(bridge: str, question_id: str, *,
                post: Any = _live_post) -> SEAM.LiveFn:
    """The seam's live consult for one question: each call posts the tick's
    (payload, daemon reply) pair to the bridge's ``/decide-live`` and commits the
    mapped view it returns. ANY failure — a down bridge, a dead/timed-out engine
    (``ok: false``), a malformed reply — returns the DECLARED abstain with
    :data:`~life_agent.core.seam.GATE_ENGINE_DOWN` named, the posterior fields kept so
    the abstain renders honestly."""

    def consult(payload: dict[str, Any],
                reply: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        try:
            resp = post(f"{bridge}/decide-live",
                        {"question_id": question_id, "payload": payload, "dec": reply})
        except Exception:
            resp = None
        if (not isinstance(resp, dict) or not resp.get("ok")
                or not isinstance(resp.get("dec"), dict)):
            return _withhold(reply, "abstain"), SEAM.GATE_ENGINE_DOWN
        return resp["dec"], None

    return consult
