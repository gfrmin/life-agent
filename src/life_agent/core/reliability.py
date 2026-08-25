"""One reliability posterior behind the seam (D-2, design §3.2; r13/M3).

Every edge's "P(this channel's report is right)" is the SAME belief shape: a Beta prior
declared once per ``(edge, cell)`` in :data:`PRIORS`, conditioned OVER THE WIRE on that
edge's graded 0/1 outcome stream (Invariant 1: ``condition`` is the one learning
mechanism, even though Beta-Bernoulli conjugacy is exact), and read back as an exact
parameterisation (:func:`reliability`) or a mean (via :func:`conditioned_state` — the
string-blind bridge relays a scalar). The instruments keep their declared stream
selectors (§3.3 observation-model clauses: identity-filtered, pure data-reading) and
pass the stream in; the fold lives here, once.

``CAL.fit_reliability_curve`` is the confidence-conditioned view of the same posterior
with monotone smoothing — the named debt (§6.3), not a second fold.
"""
from __future__ import annotations

from life_agent.core.brain import Brain

#: The one prior table, keyed (edge, cell) — each row is where an edge's trust STARTS,
#: wide on purpose (the refuted fiat Beta(17,3) taught that trust is earned from
#: evidence). ("extract", "value"): the local extractor, one cell. ("eval_claim", *):
#: the claim instrument's closed audit partition — a verified span can still be the
#: wrong subject's value (construct validity), the unsupported gate has known false
#: positives, and the unverifiable cell stays near its prior until owner audits arrive.
PRIORS: dict[tuple[str, str], tuple[float, float]] = {
    ("extract", "value"): (4.0, 4.0),
    ("eval_claim", "verified"): (3.0, 2.0),
    ("eval_claim", "unsupported"): (1.0, 3.0),
    ("eval_claim", "unverifiable"): (2.0, 2.0),
}

_BERNOULLI: dict[str, str] = {"type": "bernoulli"}


def conditioned_state(brain: Brain, edge: str, cell: str,
                      observations: list[float]) -> str:
    """The live conditioned Beta state for ``(edge, cell)`` — the one fold. The caller
    reads it (``read_params`` for the exact posterior, ``mean`` for the scalar relay)
    and destroys it; :func:`reliability` is the exact-readback binding."""
    if (edge, cell) not in PRIORS:
        raise ValueError(
            f"undeclared reliability key ({edge!r}, {cell!r}); declared: "
            f"{sorted(PRIORS)}")
    alpha, beta = PRIORS[(edge, cell)]
    sid = brain.create_state({"type": "beta", "alpha": alpha, "beta": beta})
    for obs in observations:
        brain.condition(sid, kernel=_BERNOULLI, observation=obs)
    return sid


def reliability(brain: Brain, edge: str, cell: str,
                observations: list[float]) -> tuple[float, float]:
    """The ``(edge, cell)`` reliability posterior as exact ``(alpha, beta)`` — read via
    ``read_params`` and relayed, never a host ``a += 1`` fold."""
    sid = conditioned_state(brain, edge, cell, observations)
    try:
        spec = brain.read_params(sid)
        return float(spec["alpha"]), float(spec["beta"])
    finally:
        brain.destroy_state(sid)
