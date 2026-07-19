"""The membrane shadow mirror — fans every real `/decide` tick out to the shadow's
`/decide-support`, off the answer path. This is the ONE implementation of the seam;
every production caller of :func:`life_agent.core.executor.decide_via_loop`
(``scripts/ask.py``, ``scripts/eval_executor.py``,
:mod:`life_agent.core.ask_client`) installs :func:`shadow_wrapped_post` from here, so the
safety contract — URL gating, the ``None``-response skip, exception-swallowing, request/
response identity, and the timeout/breaker below — lives in exactly one place instead of
three hand-synced copies.

The mirror leg must never delay an already-computed answer. Two guards enforce that:

1. **Its own short timeout.** Every real leg's poster in this codebase runs on a 300s
   timeout. Reusing that poster for the mirror means a bridge that is up but wedged
   (``BridgeServer`` is single-threaded by design) can hold up an already-computed answer
   for up to 300s per decide tick. The mirror instead posts on :data:`MIRROR_TIMEOUT_S` —
   short enough that a full stall is a rounding error next to the real leg's own latency.
2. **A one-strike circuit breaker per wrapped post.** If the mirror ever fails or times out
   once, the wrapper stops trying to mirror for the remainder of that question (grow
   escalation and tier corroboration can re-decide several times per question) — so a
   wedged bridge costs at most one short timeout per question, not one per decide tick.
"""
from __future__ import annotations

import contextlib
import json
import urllib.request
from typing import Any

from life_agent.core import executor as EX
from life_agent.core import seam as SEAM

# Short, and strictly less than every real-leg poster's own (300s) timeout — see module
# docstring. A wedged-but-up bridge can cost at most this much, once, per question.
MIRROR_TIMEOUT_S = 2.0


def _default_mirror_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """The mirror leg's own transport — same urllib idiom as every real-leg poster, but
    bounded to :data:`MIRROR_TIMEOUT_S` so it can never sit on the answer path. Never reuse
    a real-leg ``post`` for this — those run on a 300s timeout."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=MIRROR_TIMEOUT_S) as r:
        out: dict[str, Any] | None = json.loads(r.read())
        return out


def mirror_decide(mirror_post: EX.Post, bridge: str, question_id: str, url: str,
                  body: dict[str, Any], resp: dict[str, Any] | None) -> bool:
    """Fan one real `/decide` tick out to the membrane shadow's `/decide-support` — fires
    only for the executor's `/decide` calls (never `/route`, `/retrieve`, ...) and only when
    the daemon actually answered (``resp is None`` is the executor's own down/failure shape
    — nothing to mirror). Posts on ``mirror_post``, never the real leg's own poster.

    Returns ``True`` unless the mirror post itself raised — a skip (wrong URL, or nothing to
    mirror) also returns ``True``, since that is not a mirror failure. The caller
    (:func:`shadow_wrapped_post`) uses the return value to drive its circuit breaker; this
    function itself never raises."""
    if not url.endswith(SEAM.DECIDE_PATH) or resp is None:
        return True
    try:
        mirror_post(f"{bridge}/decide-support",
                   {"question_id": question_id, "payload": body, "dec": resp})
        return True
    except Exception:
        return False


def mirror_gate(bridge: str, question_id: str, gate: str, *,
                mirror_post: EX.Post = _default_mirror_post) -> None:
    """Fan one seam gate pre-emption out to the shadow's `/gate-support` (M2 advisory) —
    fired at the two declared-gate commit sites (`scripts/ask.py`'s weak-retrieval and
    executor-down observations into `core.seam.commit`), AFTER the gate's abstain is
    already committed, so it can never alter or delay the act. Fail-open and one-shot on
    the mirror leg's own short-timeout transport (never a real-leg poster): a down bridge
    is an instant connection refusal, a wedged one costs at most `MIRROR_TIMEOUT_S` once
    (gates fire at most once per question, so no breaker is needed)."""
    with contextlib.suppress(Exception):
        mirror_post(f"{bridge}/gate-support", {"question_id": question_id, "gate": gate})


def shadow_wrapped_post(post: EX.Post, bridge: str, question_id: str, *,
                        mirror_post: EX.Post = _default_mirror_post) -> EX.Post:
    """Wrap an executor ``Post`` so every call still forwards unchanged — same request, same
    response, same real-leg exceptions — while each `/decide` tick additionally fans out to
    the shadow AFTER the real answer is already in hand, so the mirror can never alter or
    delay it.

    ``mirror_post`` is a SEPARATE, short-timeout transport (never ``post`` itself — see
    module docstring), overridable only for tests. A one-strike breaker (a plain flag in
    this closure — the wrapper is called from one thread only, so no lock is needed) stops
    mirroring for the rest of this wrapped post's life the first time the mirror fails or
    times out, so a wedged bridge costs at most one short timeout per question."""
    tripped = False

    def wrapped(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal tripped
        resp = post(url, body)
        if not tripped and not mirror_decide(mirror_post, bridge, question_id, url, body, resp):
            tripped = True
        return resp

    return wrapped
