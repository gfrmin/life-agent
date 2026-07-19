"""The ONE act-committing seam — roadmap M0 (gold-standard roadmap, 2026-07-19).

Every act the system commits passes through :func:`commit` — there is no second
place a decision becomes an action:

* **P1 (in-process credence skin):** the lookup family's response `optimise` and the
  narrative family's per-claim `optimise{include, withhold}` — a :class:`SkinOptimise`
  request, one ``brain.optimise`` call.
* **P2 (credence daemon):** the executor loop's ``POST {daemon}/decide`` — a
  :class:`DaemonDecide` request over the caller's injected transport (the membrane
  shadow mirror wraps that transport and recognises decide ticks by
  :data:`DECIDE_PATH`, so mirroring is untouched by this seam).
* **Pre-empting gates:** the host observations that used to fork *around* the
  deciders (weak retrieval, executor down) are now **declared** into the seam via
  ``gates=`` — the seam chooses abstain from the observation; the host obeys the
  returned act instead of denying the question in a scattered ``if``.

M0 is behaviour-preserving: on every dispatch the seam does exactly what the old
call site did, byte-for-byte on the wire. What changes is topology — the forks
become data at one auditable choke point, the shape later stages re-point at the
proplang engine (M2 advisory, M3 live). A ``.optimise(`` call or a ``/decide`` POST
anywhere else in ``src/life_agent`` is a doctrine bug, enforced by the drift gate in
``tests/test_seam.py``.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from life_agent.core.brain import Brain

# The daemon decide endpoint path — single-source (the shadow mirror recognises decide
# ticks by this suffix; the drift gate keeps the literal out of every other module).
DECIDE_PATH = "/decide"

# The declared pre-empting observations (M0's two; later stages add to this vocabulary).
GATE_WEAK_RETRIEVAL = "weak_retrieval"   # retrieval cleared no chunk above the floor
GATE_EXECUTOR_DOWN = "executor_down"     # the daemon/bridge stack is unreachable

# The executor's transport seam shape (executor.Post, restated to avoid an import cycle).
Post = Callable[[str, dict[str, Any]], "dict[str, Any] | None"]


@dataclass(frozen=True)
class SkinOptimise:
    """A P1 act request: one ``brain.optimise`` on a live state — the engine picks the
    act, the seam commits it. ``brain`` is any object with the Brain ``optimise``
    protocol (tests inject conjugate doubles)."""
    brain: Brain
    state_id: str
    actions: dict[str, Any]
    preference: dict[str, Any]


@dataclass(frozen=True)
class DaemonDecide:
    """A P2 act request: one ``POST {daemon}{DECIDE_PATH}`` over the injected
    transport. The reply object is the daemon's decision view, passed through
    verbatim as :attr:`SeamDecision.view`."""
    post: Post
    daemon: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SeamDecision:
    """The committed act. ``action`` is verbatim from the decider (``report_j`` stays
    ``report_j`` — label mapping is the caller's render concern). ``gate`` names the
    declared observation that decided, when one did; ``view`` carries the daemon's
    full reply for P2."""
    action: Any
    eu: float | None
    gate: str | None = None
    view: dict[str, Any] | None = None


def commit(request: SkinOptimise | DaemonDecide | None, *,
           gates: Sequence[str] = ()) -> SeamDecision:
    """Commit exactly one act. A declared gate observation pre-empts: the seam chooses
    abstain from the observation alone (today's behaviour, made visible), naming the
    gate in the decision. Otherwise dispatch on the request kind. A call with neither
    a request nor a gate has nothing to decide — a contract error, asserted."""
    if gates:
        return SeamDecision(action="abstain", eu=None, gate=gates[0])
    assert request is not None, "commit() needs a request or a declared gate"
    if isinstance(request, SkinOptimise):
        action, eu = request.brain.optimise(
            request.state_id, actions=request.actions, preference=request.preference)
        return SeamDecision(action=action, eu=eu)
    reply = request.post(f"{request.daemon}{DECIDE_PATH}", request.payload)
    assert reply is not None, f"{request.daemon}{DECIDE_PATH} returned null"
    raw_eu = reply.get("eu")
    return SeamDecision(action=reply["effector"],
                        eu=float(raw_eu) if raw_eu is not None else None, view=reply)
