"""One reliability posterior per edge (D-2, design §3.2).

Every edge's "P(this channel's report is right)" is the same belief shape: a Beta prior
declared once per ``(edge, cell)`` in :data:`PRIORS`, conditioned on that edge's graded 0/1
outcome stream. Beta-Bernoulli is conjugate, so the fold is exact: each outcome adds itself
to alpha and its complement to beta. The instruments keep their declared stream selectors
(identity-filtered, pure data-reading) and pass the stream in; the fold lives here, once.

``CAL.fit_reliability_curve`` is the confidence-conditioned view of the same posterior
with monotone smoothing — the named debt (§6.3), not a second fold.
"""
from __future__ import annotations

from collections.abc import Iterable

from life_agent.core import pricing as PRC

#: The prior column of the ONE price table (core/pricing.RELIABILITY_PRIORS): the data
#: lives with the other priced rows; the fold lives here. Same object, one spelling.
PRIORS: dict[tuple[str, str], tuple[float, float]] = PRC.RELIABILITY_PRIORS


def reliability(edge: str, cell: str, observations: Iterable[float]) -> tuple[float, float]:
    """The ``(edge, cell)`` reliability posterior as exact ``(alpha, beta)``."""
    if (edge, cell) not in PRIORS:
        raise ValueError(
            f"undeclared reliability key ({edge!r}, {cell!r}); declared: "
            f"{sorted(PRIORS)}")
    alpha, beta = PRIORS[(edge, cell)]
    for obs in observations:
        alpha += obs
        beta += 1.0 - obs
    return alpha, beta


def mean(edge: str, cell: str, observations: Iterable[float]) -> float:
    """The posterior mean: the scalar the string-blind bridge relays."""
    alpha, beta = reliability(edge, cell, observations)
    return alpha / (alpha + beta)
