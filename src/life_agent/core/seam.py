"""The ONE act-committing seam: every act the system commits passes through :func:`commit`.

* **The decider:** the executor loop's ``POST {bridge}/decide`` — a :class:`Decide` request
  over the caller's injected transport. The bridge's decider (the candidate posterior, then
  :func:`life_agent.core.decide.bayes_act`) ranks; the reply view is the committed act.
* **Declared gates:** a host observation that pre-empts any ranking (the stack is down) is
  declared into the seam via ``gates=`` — the seam commits abstain from the observation and
  names the gate, instead of a scattered ``if`` refusing the question.

A ``/decide`` POST anywhere else in ``src/life_agent`` is a doctrine bug, enforced by the
drift gate in ``tests/test_seam.py``.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

# The decide endpoint path — single-source (the drift gate keeps the literal out of every
# other module).
DECIDE_PATH = "/decide"

# The declared unavailability observation (register §6.5): when no decider is reachable
# there is no ranking to be inside of — the record is an unavailability event, never an
# abstain decision.
GATE_EXECUTOR_DOWN = "executor_down"     # the bridge or its decider is unreachable

# The executor's transport seam shape (executor.Post, restated to avoid an import cycle).
Post = Callable[[str, dict[str, Any]], "dict[str, Any] | None"]


@dataclass(frozen=True)
class Decide:
    """One ``POST {bridge}{DECIDE_PATH}`` over the injected transport. The reply object is
    the decider's view, passed through verbatim as :attr:`SeamDecision.view`."""
    post: Post
    bridge: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SeamDecision:
    """The committed act. ``action`` is the decider's effector; ``gate`` names the declared
    observation that decided, when one did; ``view`` carries the decider's full reply."""
    action: Any
    eu: float | None
    gate: str | None = None
    view: dict[str, Any] | None = None


def commit(request: Decide | None, *,
           gates: Sequence[str] = ()) -> SeamDecision:
    """Commit exactly one act. A declared gate observation pre-empts: the seam chooses
    abstain from the observation alone, naming the gate. Otherwise the decider decides. A
    call with neither a request nor a gate has nothing to decide — a contract error."""
    if gates:
        return SeamDecision(action="abstain", eu=None, gate=gates[0])
    assert request is not None, "commit() needs a request or a declared gate"
    reply = request.post(f"{request.bridge}{DECIDE_PATH}", request.payload)
    assert reply is not None, f"{request.bridge}{DECIDE_PATH} returned null"
    raw_eu = reply.get("eu")
    return SeamDecision(action=reply["effector"],
                        eu=float(raw_eu) if raw_eu is not None else None, view=reply)
